#include "ggml.h"
#include "ggml-cpu/quants.h"

#include <riscv_vector.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

static constexpr int MAX_R = 8;
static constexpr int MAX_T = 8;

static float value_at(int i) {
    uint32_t x = (uint32_t) i * 1664525u + 1013904223u;
    x ^= x >> 16;
    const int centered = (int) (x % 2001u) - 1000;
    return (float) centered / 1000.0f;
}

static void fill_float(std::vector<float> & v, int seed) {
    for (size_t i = 0; i < v.size(); ++i) {
        v[i] = value_at((int) i + seed);
    }
}

static double seconds_now() {
    using clock = std::chrono::steady_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

#define VC_LOAD_Q4(PFX, XBLOCK) do { \
    const size_t PFX##_vl = QK4_0 / 2; \
    const vuint8m1_t PFX##_packed = __riscv_vle8_v_u8m1((XBLOCK).qs, PFX##_vl); \
    const vuint8m1_t PFX##_low_u = __riscv_vand_vx_u8m1(PFX##_packed, 0x0F, PFX##_vl); \
    const vuint8m1_t PFX##_high_u = __riscv_vsrl_vx_u8m1(PFX##_packed, 0x04, PFX##_vl); \
    const vint8m1_t PFX##_low_i = __riscv_vreinterpret_v_u8m1_i8m1(PFX##_low_u); \
    const vint8m1_t PFX##_high_i = __riscv_vreinterpret_v_u8m1_i8m1(PFX##_high_u); \
    PFX##_lo = __riscv_vsub_vx_i8m1(PFX##_low_i, 8, PFX##_vl); \
    PFX##_hi = __riscv_vsub_vx_i8m1(PFX##_high_i, 8, PFX##_vl); \
    PFX##_d = ggml_fp16_to_fp32((XBLOCK).d); \
} while (0)

#define VC_LOAD_Q8(PFX, YBLOCK) do { \
    const size_t PFX##_vl = QK8_0 / 2; \
    PFX##_lo = __riscv_vle8_v_i8m1((YBLOCK).qs, PFX##_vl); \
    PFX##_hi = __riscv_vle8_v_i8m1((YBLOCK).qs + 16, PFX##_vl); \
    PFX##_d = ggml_fp16_to_fp32((YBLOCK).d); \
} while (0)

#define VC_ACCUM(ACC, X, Y) do { \
    const size_t vc_vl = QK8_0 / 2; \
    const vint16m2_t vc_mul_lo = __riscv_vwmul_vv_i16m2(X##_lo, Y##_lo, vc_vl); \
    const vint16m2_t vc_mul = __riscv_vwmacc_vv_i16m2(vc_mul_lo, X##_hi, Y##_hi, vc_vl); \
    const vint32m1_t vc_zero = __riscv_vmv_v_x_i32m1(0, vc_vl); \
    const vint32m1_t vc_red = __riscv_vwredsum_vs_i16m2_i32m1(vc_mul, vc_zero, vc_vl); \
    const int vc_sumi = __riscv_vmv_x_s_i32m1_i32(vc_red); \
    (ACC) += (float) vc_sumi * X##_d * Y##_d; \
} while (0)

static inline const block_q4_0 & get_weight_plain(
        const std::vector<block_q4_0> & weights,
        int nb,
        int row,
        int b) {
    return weights[(size_t) row * nb + b];
}

static inline const block_q4_0 & get_weight_rowblocked(
        const std::vector<block_q4_0> & packed_weights,
        int nb,
        int R,
        int row_group,
        int rr,
        int b) {
    return packed_weights[((size_t) row_group * nb + b) * R + rr];
}

static inline const block_q8_0 & get_rhs_plain(
        const std::vector<block_q8_0> & rhs,
        int nb,
        int token,
        int b) {
    return rhs[(size_t) token * nb + b];
}

static inline const block_q8_0 & get_rhs_packed(
        const std::vector<block_q8_0> & packed_rhs,
        int T,
        int token,
        int b) {
    return packed_rhs[(size_t) b * T + token];
}

static void pack_rhs(
        const std::vector<block_q8_0> & rhs,
        std::vector<block_q8_0> & packed_rhs,
        int nb,
        int T) {
    packed_rhs.resize((size_t) nb * T);
    for (int b = 0; b < nb; ++b) {
        for (int t = 0; t < T; ++t) {
            packed_rhs[(size_t) b * T + t] = rhs[(size_t) t * nb + b];
        }
    }
}

static void pack_weights_rowblocked(
        const std::vector<block_q4_0> & weights,
        std::vector<block_q4_0> & packed_weights,
        int nb,
        int rows,
        int R) {
    const int row_groups = rows / R;
    packed_weights.resize((size_t) row_groups * nb * R);
    for (int rg = 0; rg < row_groups; ++rg) {
        for (int b = 0; b < nb; ++b) {
            for (int rr = 0; rr < R; ++rr) {
                packed_weights[((size_t) rg * nb + b) * R + rr] =
                    weights[(size_t) (rg * R + rr) * nb + b];
            }
        }
    }
}

static double bench_pack_rhs(
        const std::vector<block_q8_0> & rhs,
        int nb,
        int T,
        int repeats,
        int warmup,
        volatile float & sink) {
    std::vector<block_q8_0> packed;
    double total_ns = 0.0;
    for (int iter = 0; iter < warmup + repeats; ++iter) {
        const double t0 = seconds_now();
        pack_rhs(rhs, packed, nb, T);
        const double t1 = seconds_now();
        if (iter >= warmup) {
            total_ns += (t1 - t0) * 1.0e9;
        }
        sink += (float) packed.size() * 1.0e-12f;
    }
    return total_ns / repeats;
}

static double bench_pack_weights(
        const std::vector<block_q4_0> & weights,
        int nb,
        int rows,
        int R,
        int repeats,
        int warmup,
        volatile float & sink) {
    std::vector<block_q4_0> packed;
    double total_ns = 0.0;
    for (int iter = 0; iter < warmup + repeats; ++iter) {
        const double t0 = seconds_now();
        pack_weights_rowblocked(weights, packed, nb, rows, R);
        const double t1 = seconds_now();
        if (iter >= warmup) {
            total_ns += (t1 - t0) * 1.0e9;
        }
        sink += (float) packed.size() * 1.0e-12f;
    }
    return total_ns / repeats;
}

static double bench_old(
        int n,
        int rows,
        int T,
        int repeats,
        int warmup,
        const std::vector<block_q4_0> & weights,
        const std::vector<block_q8_0> & rhs,
        int nb,
        volatile float & sink) {
    double total_ns = 0.0;
    for (int iter = 0; iter < warmup + repeats; ++iter) {
        const double t0 = seconds_now();
        for (int t = 0; t < T; ++t) {
            const block_q8_0 * y = rhs.data() + (size_t) t * nb;
            for (int r = 0; r < rows; ++r) {
                float s = 0.0f;
                const block_q4_0 * x = weights.data() + (size_t) r * nb;
                ggml_vec_dot_q4_0_q8_0(n, &s, 0, x, 0, y, 0, 1);
                sink += s * 0.0000001f;
            }
        }
        const double t1 = seconds_now();
        if (iter >= warmup) {
            total_ns += (t1 - t0) * 1.0e9;
        }
    }
    return total_ns / repeats;
}

static void accumulate_group(
        int rg,
        int R,
        int T,
        bool use_packed_rhs,
        bool use_rowblocked_weights,
        const std::vector<block_q4_0> & weights,
        const std::vector<block_q4_0> & packed_weights,
        const std::vector<block_q8_0> & rhs,
        const std::vector<block_q8_0> & packed_rhs,
        int nb,
        float acc[MAX_R][MAX_T]) {
    for (int b = 0; b < nb; ++b) {
        if (T == 1) {
            const block_q8_0 & y0b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 0, b) : get_rhs_plain(rhs, nb, 0, b);
            vint8m1_t y0_lo, y0_hi;
            float y0_d;
            VC_LOAD_Q8(y0, y0b);
            for (int rr = 0; rr < R; ++rr) {
                const block_q4_0 & xb = use_rowblocked_weights
                    ? get_weight_rowblocked(packed_weights, nb, R, rg, rr, b)
                    : get_weight_plain(weights, nb, rg * R + rr, b);
                vint8m1_t x_lo, x_hi;
                float x_d;
                VC_LOAD_Q4(x, xb);
                VC_ACCUM(acc[rr][0], x, y0);
            }
        } else if (T == 2) {
            const block_q8_0 & y0b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 0, b) : get_rhs_plain(rhs, nb, 0, b);
            const block_q8_0 & y1b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 1, b) : get_rhs_plain(rhs, nb, 1, b);
            vint8m1_t y0_lo, y0_hi, y1_lo, y1_hi;
            float y0_d, y1_d;
            VC_LOAD_Q8(y0, y0b);
            VC_LOAD_Q8(y1, y1b);
            for (int rr = 0; rr < R; ++rr) {
                const block_q4_0 & xb = use_rowblocked_weights
                    ? get_weight_rowblocked(packed_weights, nb, R, rg, rr, b)
                    : get_weight_plain(weights, nb, rg * R + rr, b);
                vint8m1_t x_lo, x_hi;
                float x_d;
                VC_LOAD_Q4(x, xb);
                VC_ACCUM(acc[rr][0], x, y0);
                VC_ACCUM(acc[rr][1], x, y1);
            }
        } else if (T == 4) {
            const block_q8_0 & y0b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 0, b) : get_rhs_plain(rhs, nb, 0, b);
            const block_q8_0 & y1b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 1, b) : get_rhs_plain(rhs, nb, 1, b);
            const block_q8_0 & y2b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 2, b) : get_rhs_plain(rhs, nb, 2, b);
            const block_q8_0 & y3b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 3, b) : get_rhs_plain(rhs, nb, 3, b);
            vint8m1_t y0_lo, y0_hi, y1_lo, y1_hi, y2_lo, y2_hi, y3_lo, y3_hi;
            float y0_d, y1_d, y2_d, y3_d;
            VC_LOAD_Q8(y0, y0b);
            VC_LOAD_Q8(y1, y1b);
            VC_LOAD_Q8(y2, y2b);
            VC_LOAD_Q8(y3, y3b);
            for (int rr = 0; rr < R; ++rr) {
                const block_q4_0 & xb = use_rowblocked_weights
                    ? get_weight_rowblocked(packed_weights, nb, R, rg, rr, b)
                    : get_weight_plain(weights, nb, rg * R + rr, b);
                vint8m1_t x_lo, x_hi;
                float x_d;
                VC_LOAD_Q4(x, xb);
                VC_ACCUM(acc[rr][0], x, y0);
                VC_ACCUM(acc[rr][1], x, y1);
                VC_ACCUM(acc[rr][2], x, y2);
                VC_ACCUM(acc[rr][3], x, y3);
            }
        } else if (T == 8) {
            const block_q8_0 & y0b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 0, b) : get_rhs_plain(rhs, nb, 0, b);
            const block_q8_0 & y1b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 1, b) : get_rhs_plain(rhs, nb, 1, b);
            const block_q8_0 & y2b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 2, b) : get_rhs_plain(rhs, nb, 2, b);
            const block_q8_0 & y3b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 3, b) : get_rhs_plain(rhs, nb, 3, b);
            const block_q8_0 & y4b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 4, b) : get_rhs_plain(rhs, nb, 4, b);
            const block_q8_0 & y5b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 5, b) : get_rhs_plain(rhs, nb, 5, b);
            const block_q8_0 & y6b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 6, b) : get_rhs_plain(rhs, nb, 6, b);
            const block_q8_0 & y7b = use_packed_rhs ? get_rhs_packed(packed_rhs, T, 7, b) : get_rhs_plain(rhs, nb, 7, b);
            vint8m1_t y0_lo, y0_hi, y1_lo, y1_hi, y2_lo, y2_hi, y3_lo, y3_hi;
            vint8m1_t y4_lo, y4_hi, y5_lo, y5_hi, y6_lo, y6_hi, y7_lo, y7_hi;
            float y0_d, y1_d, y2_d, y3_d, y4_d, y5_d, y6_d, y7_d;
            VC_LOAD_Q8(y0, y0b);
            VC_LOAD_Q8(y1, y1b);
            VC_LOAD_Q8(y2, y2b);
            VC_LOAD_Q8(y3, y3b);
            VC_LOAD_Q8(y4, y4b);
            VC_LOAD_Q8(y5, y5b);
            VC_LOAD_Q8(y6, y6b);
            VC_LOAD_Q8(y7, y7b);
            for (int rr = 0; rr < R; ++rr) {
                const block_q4_0 & xb = use_rowblocked_weights
                    ? get_weight_rowblocked(packed_weights, nb, R, rg, rr, b)
                    : get_weight_plain(weights, nb, rg * R + rr, b);
                vint8m1_t x_lo, x_hi;
                float x_d;
                VC_LOAD_Q4(x, xb);
                VC_ACCUM(acc[rr][0], x, y0);
                VC_ACCUM(acc[rr][1], x, y1);
                VC_ACCUM(acc[rr][2], x, y2);
                VC_ACCUM(acc[rr][3], x, y3);
                VC_ACCUM(acc[rr][4], x, y4);
                VC_ACCUM(acc[rr][5], x, y5);
                VC_ACCUM(acc[rr][6], x, y6);
                VC_ACCUM(acc[rr][7], x, y7);
            }
        }
    }
}

static double bench_candidate(
        int rows,
        int R,
        int T,
        int repeats,
        int warmup,
        bool use_packed_rhs,
        bool use_rowblocked_weights,
        const std::vector<block_q4_0> & weights,
        const std::vector<block_q4_0> & packed_weights,
        const std::vector<block_q8_0> & rhs,
        const std::vector<block_q8_0> & packed_rhs,
        int nb,
        volatile float & sink) {
    const int row_groups = rows / R;
    double total_ns = 0.0;

    for (int iter = 0; iter < warmup + repeats; ++iter) {
        const double t0 = seconds_now();
        for (int rg = 0; rg < row_groups; ++rg) {
            float acc[MAX_R][MAX_T] = {};
            accumulate_group(rg, R, T, use_packed_rhs, use_rowblocked_weights,
                             weights, packed_weights, rhs, packed_rhs, nb, acc);

            float local = 0.0f;
            for (int rr = 0; rr < R; ++rr) {
                for (int tt = 0; tt < T; ++tt) {
                    local += acc[rr][tt];
                }
            }
            sink += local * 0.0000001f;
        }
        const double t1 = seconds_now();
        if (iter >= warmup) {
            total_ns += (t1 - t0) * 1.0e9;
        }
    }
    return total_ns / repeats;
}

static void check_candidate(
        int n,
        int rows,
        int R,
        int T,
        bool use_packed_rhs,
        bool use_rowblocked_weights,
        const std::vector<block_q4_0> & weights,
        const std::vector<block_q4_0> & packed_weights,
        const std::vector<block_q8_0> & rhs,
        const std::vector<block_q8_0> & packed_rhs,
        int nb,
        double & max_abs,
        double & max_rel) {
    const int row_groups = rows / R;

    for (int rg = 0; rg < row_groups; ++rg) {
        float acc[MAX_R][MAX_T] = {};
        accumulate_group(rg, R, T, use_packed_rhs, use_rowblocked_weights,
                         weights, packed_weights, rhs, packed_rhs, nb, acc);

        for (int rr = 0; rr < R; ++rr) {
            const int row = rg * R + rr;
            const block_q4_0 * x = weights.data() + (size_t) row * nb;
            for (int tt = 0; tt < T; ++tt) {
                float ref = 0.0f;
                const block_q8_0 * y = rhs.data() + (size_t) tt * nb;
                ggml_vec_dot_q4_0_q8_0(n, &ref, 0, x, 0, y, 0, 1);
                const double diff = std::fabs((double) ref - (double) acc[rr][tt]);
                const double denom = std::fabs((double) ref) + 1.0e-9;
                max_abs = std::fmax(max_abs, diff);
                max_rel = std::fmax(max_rel, diff / denom);
            }
        }
    }
}

static void print_matrix_row(
        const char * layout,
        int R,
        int T,
        int n,
        int rows,
        int repeats,
        double avg_ns,
        double old_t1_ns,
        double old_t_ns,
        double max_abs,
        double max_rel) {
    std::printf("%s,%d,%d,%d,%d,%d,%.0f,%.3f,%.3f,%.3f,%.9g,%.9g\n",
                layout,
                R,
                T,
                n,
                rows,
                repeats,
                avg_ns,
                avg_ns / 1.0e6,
                avg_ns / old_t1_ns,
                avg_ns / old_t_ns,
                max_abs,
                max_rel);
}

static void print_layout_row(
        const char * layout,
        int R,
        int T,
        int n,
        int rows,
        int repeats,
        double pack_rhs_ns,
        double pack_weight_ns,
        double kernel_ns,
        double old_t1_ns,
        double old_t_ns,
        double max_abs,
        double max_rel) {
    const double total_ns = pack_rhs_ns + pack_weight_ns + kernel_ns;
    std::printf("%s,%d,%d,%d,%d,%d,%.0f,%.0f,%.0f,%.0f,%.3f,%.3f,%.3f,%.9g,%.9g\n",
                layout,
                R,
                T,
                n,
                rows,
                repeats,
                pack_rhs_ns,
                pack_weight_ns,
                kernel_ns,
                total_ns,
                total_ns / 1.0e6,
                total_ns / old_t1_ns,
                total_ns / old_t_ns,
                max_abs,
                max_rel);
}

int main(int argc, char ** argv) {
    int n = 11008;
    int rows = 512;
    int repeats = 3;
    int warmup = 1;

    if (argc > 1) {
        n = std::atoi(argv[1]);
    }
    if (argc > 2) {
        rows = std::atoi(argv[2]);
    }
    if (argc > 3) {
        repeats = std::atoi(argv[3]);
    }
    if (argc > 4) {
        warmup = std::atoi(argv[4]);
    }

    if (n <= 0 || rows <= 0 || repeats <= 0 || warmup < 0 ||
            n % QK4_0 != 0 || n % QK8_0 != 0 || rows % MAX_R != 0) {
        std::fprintf(stderr, "bad args: n=%d rows=%d repeats=%d warmup=%d\n", n, rows, repeats, warmup);
        return 2;
    }

    const int nb = n / QK4_0;
    std::vector<block_q4_0> weights((size_t) rows * nb);
    std::vector<block_q8_0> rhs((size_t) MAX_T * nb);
    std::vector<float> tmp((size_t) n);
    volatile float sink = 0.0f;

    for (int r = 0; r < rows; ++r) {
        fill_float(tmp, 17 + r * 13);
        quantize_row_q4_0(tmp.data(), weights.data() + (size_t) r * nb, n);
    }
    for (int t = 0; t < MAX_T; ++t) {
        fill_float(tmp, 1009 + t * 29);
        quantize_row_q8_0(tmp.data(), rhs.data() + (size_t) t * nb, n);
    }

    const int Ts[] = {1, 2, 4, 8};
    double old_ns[MAX_T + 1] = {};
    for (int T : Ts) {
        old_ns[T] = bench_old(n, rows, T, repeats, warmup, weights, rhs, nb, sink);
    }

    std::fprintf(stderr, "old_t1_ns=%.0f old_t4_ns=%.0f sink=%g\n", old_ns[1], old_ns[4], (float) sink);

    const int Rs[] = {1, 2, 4, 8};
    std::printf("kind,layout,R,T,n,rows,repeats,avg_ns,avg_ms,ratio_vs_old_t1,ratio_vs_old_T,max_abs,max_rel\n");
    for (int R : Rs) {
        for (int T : Ts) {
            std::vector<block_q8_0> packed_rhs;
            std::vector<block_q4_0> packed_weights;
            pack_rhs(rhs, packed_rhs, nb, T);
            pack_weights_rowblocked(weights, packed_weights, nb, rows, R);

            double max_abs = 0.0;
            double max_rel = 0.0;
            check_candidate(n, rows, R, T, false, false, weights, packed_weights, rhs, packed_rhs, nb, max_abs, max_rel);
            const double ns = bench_candidate(rows, R, T, repeats, warmup, false, false,
                                              weights, packed_weights, rhs, packed_rhs, nb, sink);

            std::printf("matrix,");
            print_matrix_row("no_pack", R, T, n, rows, repeats, ns, old_ns[1], old_ns[T], max_abs, max_rel);
        }
    }

    std::printf("kind,layout,R,T,n,rows,repeats,C_pack_rhs_ns,C_pack_weight_once_ns,C_kernel_ns,C_total_ns,C_total_ms,ratio_vs_old_t1,ratio_vs_old_T,max_abs,max_rel\n");
    for (int R : Rs) {
        const int T = 4;
        std::vector<block_q8_0> packed_rhs;
        std::vector<block_q4_0> packed_weights;
        pack_rhs(rhs, packed_rhs, nb, T);
        pack_weights_rowblocked(weights, packed_weights, nb, rows, R);

        const double rhs_pack_ns = bench_pack_rhs(rhs, nb, T, repeats, warmup, sink);
        const double weight_pack_ns = bench_pack_weights(weights, nb, rows, R, repeats, warmup, sink);

        const struct layout_case {
            const char * name;
            bool packed_rhs;
            bool rowblocked_weights;
        } cases[] = {
            {"Layout0_no_packing", false, false},
            {"Layout1_packed_rhs", true, false},
            {"Layout2_rowblocked_weights", false, true},
            {"Layout3_packed_rhs_rowblocked_weights", true, true},
        };

        for (const auto & c : cases) {
            double max_abs = 0.0;
            double max_rel = 0.0;
            check_candidate(n, rows, R, T, c.packed_rhs, c.rowblocked_weights,
                            weights, packed_weights, rhs, packed_rhs, nb, max_abs, max_rel);
            const double kernel_ns = bench_candidate(rows, R, T, repeats, warmup,
                                                     c.packed_rhs, c.rowblocked_weights,
                                                     weights, packed_weights, rhs, packed_rhs, nb, sink);
            const double charge_rhs = c.packed_rhs ? rhs_pack_ns : 0.0;
            const double charge_weight = c.rowblocked_weights ? weight_pack_ns : 0.0;

            std::printf("layout,");
            print_layout_row(c.name, R, T, n, rows, repeats,
                             charge_rhs, charge_weight, kernel_ns,
                             old_ns[1], old_ns[T], max_abs, max_rel);
        }
    }

    if (std::isnan((float) sink)) {
        std::fprintf(stderr, "sink is nan\n");
        return 3;
    }

    return 0;
}
