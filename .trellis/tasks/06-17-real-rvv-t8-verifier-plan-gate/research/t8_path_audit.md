# T8 Path Audit

Date: 2026-06-17 Asia/Shanghai

## Remote Tree

```text
remote: rvv
task directory: /home/ubuntu/vericurve-rv-lab/real-rvv-t8-gate
source tree: /home/ubuntu/vericurve-rv-lab/llama.cpp
llama.cpp commit: e36a602ba38a26206c749ba4fb5dcf481bfd92db
build dir: /home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve
GGML_RVV: ON
GGML_BLAS: OFF
GGML_CPU_REPACK: ON
GGML_NATIVE: OFF
```

The llama.cpp tree has existing instrumentation changes in:

```text
examples/lookup/lookup-stats.cpp
ggml/src/ggml-cpu/arch/riscv/quants.c
ggml/src/ggml-cpu/repack.cpp
```

This task did not modify that tree. The new harness was copied to:

```text
/home/ubuntu/vericurve-rv-lab/real-rvv-t8-gate/scripts/bench_t8_verifier_plan.cpp
```

## Existing Harness

Existing remote source:

```text
/home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel.cpp
```

Existing T8 route classification:

```text
current matrix R8,T8 no_pack: native R8T8 no-pack
current layout section: T=4 only
current T8 rowblocked/packed layout: not measured before this task
current composed two-T4 T8: not measured before this task
current T16 in prior CSV: composed estimate from two measured R8T8 tiles
```

Therefore, the previous T8 evidence was insufficient:

```text
native R8T8 no-pack existed, but optimized T8 verifier plans were not explored.
The decisive missing cases were native T8 with rowblocked weights / packed RHS
and a real two-T4 composed T8 path measured inside one harness.
```

## Task Harness Changes

Compared with `bench_rtile_ttile_kernel.cpp`, the task harness adds:

```text
MAX_R = 16
R candidates = {1,2,4,8,16}
native T8 layout candidates:
  no_pack
  packed_rhs
  rowblocked_weights
  packed_rhs_rowblocked_weights
composed T8 candidates:
  two real T4 calls in one measured path
  with the same four layout options
separate pack RHS / pack weights / kernel timing
correctness max_abs / max_rel against old q4_0 x q8_0 vecdot
```

Patch artifact:

```text
patches/t8_verifier_plan.patch
```

## Compile Command

```bash
cd ~/vericurve-rv-lab/llama.cpp
nice -n 10 timeout 180 g++ -std=c++17 -O3 \
  -march=rv64gcv_zfh_zvfh_zicbop_zihintpause -mabi=lp64d \
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/include \
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/src \
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/src/ggml-cpu \
  /home/ubuntu/vericurve-rv-lab/real-rvv-t8-gate/scripts/bench_t8_verifier_plan.cpp \
  -L/home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve/bin \
  -lggml-cpu -lggml-base -lggml \
  -Wl,-rpath,/home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve/bin \
  -o /home/ubuntu/vericurve-rv-lab/real-rvv-t8-gate/bench_t8_verifier_plan
```

Compile result:

```text
exit code: 0
```

## Run Commands

Rows512:

```bash
cd ~/vericurve-rv-lab/real-rvv-t8-gate
OMP_NUM_THREADS=1 nice -n 10 timeout 600 ./bench_t8_verifier_plan 11008 512 5 1 \
  > results/real_rvv_t8_curve_raw_rows512.csv \
  2> artifacts/real_rvv_t8_curve_rows512.stderr
```

Rows2048:

```bash
cd ~/vericurve-rv-lab/real-rvv-t8-gate
OMP_NUM_THREADS=1 nice -n 10 timeout 800 ./bench_t8_verifier_plan 11008 2048 3 1 \
  > results/real_rvv_t8_curve_raw_rows2048.csv \
  2> artifacts/real_rvv_t8_curve_rows2048.stderr
```

Raw local copies:

```text
artifacts/real_rvv_t8_curve_raw_rows512.csv
artifacts/real_rvv_t8_curve_rows512.stderr
artifacts/real_rvv_t8_curve_raw_rows2048.csv
artifacts/real_rvv_t8_curve_rows2048.stderr
```
