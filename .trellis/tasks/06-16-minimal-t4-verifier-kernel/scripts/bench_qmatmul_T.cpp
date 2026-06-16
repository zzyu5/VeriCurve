#include "ggml-cpu/quants.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <vector>

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

int main(int argc, char ** argv) {
    int n = 11008;
    int rows = 512;
    int repeats = 5;
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

    if (n <= 0 || rows <= 0 || repeats <= 0 || n % QK4_0 != 0 || n % QK8_0 != 0) {
        std::fprintf(stderr, "bad args: n=%d rows=%d repeats=%d\n", n, rows, repeats);
        return 2;
    }

    const int nb4 = n / QK4_0;
    const int nb8 = n / QK8_0;

    std::vector<block_q4_0> weights((size_t) rows * nb4);
    std::vector<block_q8_0> rhs((size_t) 16 * nb8);
    std::vector<float> tmp((size_t) n);
    std::vector<float> out((size_t) rows * 16);

    for (int r = 0; r < rows; ++r) {
        fill_float(tmp, 17 + r * 13);
        quantize_row_q4_0(tmp.data(), weights.data() + (size_t) r * nb4, n);
    }

    for (int t = 0; t < 16; ++t) {
        fill_float(tmp, 1009 + t * 29);
        quantize_row_q8_0(tmp.data(), rhs.data() + (size_t) t * nb8, n);
    }

    const int Ts[] = {1, 2, 4, 8, 16};
    double base_ns = 0.0;
    volatile float sink = 0.0f;

    std::printf("T,n,rows,repeats,avg_ns,avg_ms,total_ratio,per_token_ns,path\n");

    for (int ti = 0; ti < 5; ++ti) {
        const int T = Ts[ti];
        double total_ns = 0.0;

        for (int iter = 0; iter < warmup + repeats; ++iter) {
            const double t0 = seconds_now();

            for (int t = 0; t < T; ++t) {
                const block_q8_0 * y = rhs.data() + (size_t) t * nb8;
                for (int r = 0; r < rows; ++r) {
                    float s = 0.0f;
                    const block_q4_0 * x = weights.data() + (size_t) r * nb4;
                    ggml_vec_dot_q4_0_q8_0(n, &s, 0, x, 0, y, 0, 1);
                    out[(size_t) r * 16 + t] = s;
                    sink += s * 0.0000001f;
                }
            }

            const double t1 = seconds_now();
            if (iter >= warmup) {
                total_ns += (t1 - t0) * 1.0e9;
            }
        }

        const double avg_ns = total_ns / repeats;
        if (ti == 0) {
            base_ns = avg_ns;
        }
        std::printf("%d,%d,%d,%d,%.0f,%.3f,%.3f,%.0f,ggml_vec_dot_q4_0_q8_0_nrc1\n",
                    T,
                    n,
                    rows,
                    repeats,
                    avg_ns,
                    avg_ns / 1.0e6,
                    avg_ns / base_ns,
                    avg_ns / T);
    }

    if (std::isnan((float) sink)) {
        std::fprintf(stderr, "sink is nan\n");
        return 3;
    }

    return 0;
}
