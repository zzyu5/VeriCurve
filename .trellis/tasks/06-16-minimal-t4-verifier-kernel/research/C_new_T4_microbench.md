# C_new(4) Minimal T4 Microbenchmark

## Decision

```text
Task 3 label: NO-GO for current minimal direct-vecdot T4 path
Controller label: do not proceed
Full-system label: NO-GO under this minimal T4 gate
```

This is not a proof that every possible T-specialized RVV kernel is impossible.
It is a completed Go/No-Go result for the minimal direct Q4_0 x Q8_0 T4 design
specified in this task.

## Source and Build

Source:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/scripts/bench_t4_kernel.cpp
```

Remote compile command:

```bash
g++ -std=c++17 -O3 \
  -march=rv64gcv_zfh_zvfh_zicbop_zihintpause -mabi=lp64d \
  -Iggml/include -Iggml/src -Iggml/src/ggml-cpu \
  "$HOME/vericurve-rv-lab/minimal-t4/bench_t4_kernel.cpp" \
  -Lbuild-vericurve/bin \
  -lggml-cpu -lggml-base -lggml \
  -Wl,-rpath,"$HOME/vericurve-rv-lab/llama.cpp/build-vericurve/bin" \
  -o "$HOME/vericurve-rv-lab/minimal-t4/bench_t4_kernel"
```

Compile result:

```text
exit code: 0
```

## Measurement

Remote command:

```bash
cd "$HOME/vericurve-rv-lab/minimal-t4"
GGML_VERICURVE_TRACE=1 nice -n 10 timeout 300 \
  ./bench_t4_kernel 11008 512 5 \
  > results/C_new_T4_microbench.csv \
  2> artifacts/C_new_T4_microbench.stderr
```

Parameters:

```text
n = 11008
rows = 512
repeats = 5
warmup = 1
threads = 1 by construction
old_t1 = one ggml_vec_dot_q4_0_q8_0 per row
old_t4 = four ggml_vec_dot_q4_0_q8_0 calls per row
new_t4 = harness-local q4_0_q8_0_dot_t4_rvv per row
```

Raw artifacts:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/C_new_T4_microbench.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/C_new_T4_microbench.stderr
.trellis/tasks/06-16-minimal-t4-verifier-kernel/patches/t4_kernel_minimal.patch
```

## Results

```text
metric,n,rows,repeats,avg_ns,avg_ms,ratio_vs_old_t1,ratio_vs_old_t4,max_abs,max_rel
old_t1,11008,512,5,11737726,11.738,1.000,0.250,0,0
old_t4,11008,512,5,46889582,46.890,3.995,1.000,0,0
new_t4,11008,512,5,79464226,79.464,6.770,1.695,0,0
```

Correctness:

```text
max_abs = 0
max_rel = 0
correctness passes
```

Trace emitted by old-path calls in the harness:

```text
VERICURVE_TRACE,function=ggml_vec_dot_q4_0_q8_0,call_count=17408,last_n=11008,last_bs=0,last_nrc=1
```

## Gate Evaluation

Required `GO-system`:

```text
C_new(4) <= 2.6 * C_old(1)
and C_new(4) <= 0.70 * C_old(4)
```

Observed:

```text
C_new(4) = 6.770 * C_old(1)
C_new(4) = 1.695 * C_old(4)
```

Required `NO-GO for VeriCurve system`:

```text
C_new(4) > 3.2 * C_old(1)
and C_new(4) > 0.85 * C_old(4)
```

Observed result satisfies the No-Go condition.

## Interpretation

The minimal direct T4 kernel reuses Q4 load/decode, but that reuse is not enough
to offset the cost of four RHS multiply/reduce paths and the resulting register
pressure/codegen overhead. The current old path is already highly optimized for
single-RHS `nrc=1`, and the naive T4 dataflow is slower than calling it four
times.

This blocks the full VeriCurve-RV system track as currently scoped:

```text
Do not proceed to controller work.
Do not claim curve-aware speculation system GO.
```

The only technically defensible continuation would be a narrower kernel
research branch with a stronger data layout or accumulation strategy, for
example:

```text
repacked/interleaved Q8 RHS layout
scale-aware vector float accumulation
integration with existing 16x1 repack machinery
or a different low-bit quant path where T reuse is physically larger
```

Those are outside this minimal Go/No-Go task.

