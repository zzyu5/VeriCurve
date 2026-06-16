#!/usr/bin/env python3
from pathlib import Path


ROOT = Path.cwd()
QUANTS = ROOT / "ggml/src/ggml-cpu/arch/riscv/quants.c"
REPACK = ROOT / "ggml/src/ggml-cpu/repack.cpp"


def patch_quants() -> None:
    text = QUANTS.read_text()
    if "VERICURVE_TRACE,function=ggml_vec_dot_q4_0_q8_0" in text:
        return

    helper = r'''
static int vc_trace_enabled_cached = -1;
static long long vc_trace_q4_0_q8_0_calls = 0;
static int vc_trace_q4_0_q8_0_last_n = 0;
static int vc_trace_q4_0_q8_0_last_nrc = 0;
static size_t vc_trace_q4_0_q8_0_last_bs = 0;

static int vc_trace_enabled(void) {
    if (vc_trace_enabled_cached < 0) {
        const char * env = getenv("GGML_VERICURVE_TRACE");
        vc_trace_enabled_cached = env && env[0] && env[0] != '0';
    }
    return vc_trace_enabled_cached;
}

static void vc_trace_dump(void) {
    if (!vc_trace_enabled() || vc_trace_q4_0_q8_0_calls == 0) {
        return;
    }
    fprintf(stderr,
            "VERICURVE_TRACE,function=ggml_vec_dot_q4_0_q8_0,call_count=%lld,last_n=%d,last_bs=%zu,last_nrc=%d\n",
            vc_trace_q4_0_q8_0_calls,
            vc_trace_q4_0_q8_0_last_n,
            vc_trace_q4_0_q8_0_last_bs,
            vc_trace_q4_0_q8_0_last_nrc);
}

static void vc_trace_vec_dot_q4_0_q8_0(int n, size_t bs, int nrc) {
    if (!vc_trace_enabled()) {
        return;
    }
    static int registered = 0;
    if (!registered) {
        atexit(vc_trace_dump);
        registered = 1;
    }
    vc_trace_q4_0_q8_0_calls++;
    vc_trace_q4_0_q8_0_last_n = n;
    vc_trace_q4_0_q8_0_last_bs = bs;
    vc_trace_q4_0_q8_0_last_nrc = nrc;
}
'''

    text = text.replace("#define UNUSED GGML_UNUSED\n", "#define UNUSED GGML_UNUSED\n" + helper, 1)
    sig = (
        "void ggml_vec_dot_q4_0_q8_0(int n, float * GGML_RESTRICT s, size_t bs, "
        "const void * GGML_RESTRICT vx, size_t bx, const void * GGML_RESTRICT vy, "
        "size_t by, int nrc) {\n"
    )
    if sig not in text:
        raise RuntimeError("q4_0_q8_0 vec_dot signature not found")
    text = text.replace(sig, sig + "    vc_trace_vec_dot_q4_0_q8_0(n, bs, nrc);\n", 1)
    QUANTS.write_text(text)


def patch_repack() -> None:
    text = REPACK.read_text()
    if "VERICURVE_TRACE,function=%s" in text:
        return

    text = text.replace('#include <cstdio>  // for GGML_ASSERT\n',
                        '#include <cstdio>  // for GGML_ASSERT\n#include <cstdlib>\n', 1)

    helper = r'''
struct vc_repack_trace_counter {
    const char * name;
    long long calls;
    int last_n;
    size_t last_bs;
    int last_nr;
    int last_nc;
};

static int vc_repack_trace_enabled_cached = -1;
static vc_repack_trace_counter vc_trace_gemv_q4_0_16x1_q8_0 = {"ggml_gemv_q4_0_16x1_q8_0", 0, 0, 0, 0, 0};
static vc_repack_trace_counter vc_trace_gemm_q4_0_16x1_q8_0 = {"ggml_gemm_q4_0_16x1_q8_0", 0, 0, 0, 0, 0};

static int vc_repack_trace_enabled() {
    if (vc_repack_trace_enabled_cached < 0) {
        const char * env = std::getenv("GGML_VERICURVE_TRACE");
        vc_repack_trace_enabled_cached = env && env[0] && env[0] != '0';
    }
    return vc_repack_trace_enabled_cached;
}

static void vc_repack_trace_dump_one(const vc_repack_trace_counter & c) {
    if (c.calls == 0) {
        return;
    }
    std::fprintf(stderr,
                 "VERICURVE_TRACE,function=%s,call_count=%lld,last_n=%d,last_bs=%zu,last_nr=%d,last_nc=%d\n",
                 c.name,
                 c.calls,
                 c.last_n,
                 c.last_bs,
                 c.last_nr,
                 c.last_nc);
}

static void vc_repack_trace_dump() {
    if (!vc_repack_trace_enabled()) {
        return;
    }
    vc_repack_trace_dump_one(vc_trace_gemv_q4_0_16x1_q8_0);
    vc_repack_trace_dump_one(vc_trace_gemm_q4_0_16x1_q8_0);
}

static void vc_repack_trace_count(vc_repack_trace_counter & c, int n, size_t bs, int nr, int nc) {
    if (!vc_repack_trace_enabled()) {
        return;
    }
    static int registered = 0;
    if (!registered) {
        std::atexit(vc_repack_trace_dump);
        registered = 1;
    }
    c.calls++;
    c.last_n = n;
    c.last_bs = bs;
    c.last_nr = nr;
    c.last_nc = nc;
}
'''
    text = text.replace("#define UNUSED GGML_UNUSED\n", "#define UNUSED GGML_UNUSED\n" + helper, 1)

    old = (
        "template <> void gemv<block_q4_0, 1, 16, GGML_TYPE_Q8_0>(int n, float * s, size_t bs, "
        "const void * vx, const void * vy, int nr, int nc) {\n"
        "    ggml_gemv_q4_0_16x1_q8_0(n, s, bs, vx, vy, nr, nc);\n"
        "}"
    )
    new = (
        "template <> void gemv<block_q4_0, 1, 16, GGML_TYPE_Q8_0>(int n, float * s, size_t bs, "
        "const void * vx, const void * vy, int nr, int nc) {\n"
        "    vc_repack_trace_count(vc_trace_gemv_q4_0_16x1_q8_0, n, bs, nr, nc);\n"
        "    ggml_gemv_q4_0_16x1_q8_0(n, s, bs, vx, vy, nr, nc);\n"
        "}"
    )
    if old not in text:
        raise RuntimeError("q4_0 16x1 gemv wrapper not found")
    text = text.replace(old, new, 1)

    old = (
        "template <> void gemm<block_q4_0, 1, 16, GGML_TYPE_Q8_0>(int n, float * s, size_t bs, "
        "const void * vx, const void * vy, int nr, int nc) {\n"
        "    ggml_gemm_q4_0_16x1_q8_0(n, s, bs, vx, vy, nr, nc);\n"
        "}"
    )
    new = (
        "template <> void gemm<block_q4_0, 1, 16, GGML_TYPE_Q8_0>(int n, float * s, size_t bs, "
        "const void * vx, const void * vy, int nr, int nc) {\n"
        "    vc_repack_trace_count(vc_trace_gemm_q4_0_16x1_q8_0, n, bs, nr, nc);\n"
        "    ggml_gemm_q4_0_16x1_q8_0(n, s, bs, vx, vy, nr, nc);\n"
        "}"
    )
    if old not in text:
        raise RuntimeError("q4_0 16x1 gemm wrapper not found")
    text = text.replace(old, new, 1)

    REPACK.write_text(text)


def main() -> None:
    patch_quants()
    patch_repack()


if __name__ == "__main__":
    main()
