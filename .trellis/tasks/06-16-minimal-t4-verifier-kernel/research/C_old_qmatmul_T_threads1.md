# ggml-Level C_old(T) Microbenchmark

## Decision

```text
Task 2 label: GO-T4-kernel
```

Reason:

```text
C_old_qmatmul(4) = 3.993 * C_old_qmatmul(1)
```

This exceeds the `GO-T4-kernel` threshold:

```text
C_old_qmatmul(4) >= 3.4 * C_old_qmatmul(1)
```

The ggml-level old path is effectively linear in T.

## Source Tree and Build

Source tree:

```text
/home/ubuntu/vericurve-rv-lab/llama.cpp
commit: e36a602
```

Benchmark source:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/scripts/bench_qmatmul_T.cpp
```

Remote compile command:

```bash
g++ -std=c++17 -O3 \
  -march=rv64gcv_zfh_zvfh_zicbop_zihintpause -mabi=lp64d \
  -Iggml/include -Iggml/src -Iggml/src/ggml-cpu \
  "$HOME/vericurve-rv-lab/minimal-t4/bench_qmatmul_T.cpp" \
  -Lbuild-vericurve/bin \
  -lggml-cpu -lggml-base -lggml \
  -Wl,-rpath,"$HOME/vericurve-rv-lab/llama.cpp/build-vericurve/bin" \
  -o "$HOME/vericurve-rv-lab/minimal-t4/bench_qmatmul_T"
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
  ./bench_qmatmul_T 11008 512 5 \
  > results/C_old_qmatmul_T_threads1.csv \
  2> artifacts/C_old_qmatmul_T_threads1.stderr
```

Parameters:

```text
n = 11008
rows = 512
repeats = 5
warmup = 1
threads = 1 by construction
quant = Q4_0 x Q8_0
path = ggml_vec_dot_q4_0_q8_0, nrc=1
```

Raw artifacts:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/C_old_qmatmul_T_threads1.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/C_old_qmatmul_T_threads1.stderr
```

## Results

```text
T,n,rows,repeats,avg_ns,avg_ms,total_ratio,per_token_ns,path
1,11008,512,5,6416102,6.416,1.000,6416102,ggml_vec_dot_q4_0_q8_0_nrc1
2,11008,512,5,12810328,12.810,1.997,6405164,ggml_vec_dot_q4_0_q8_0_nrc1
4,11008,512,5,25619756,25.620,3.993,6404939,ggml_vec_dot_q4_0_q8_0_nrc1
8,11008,512,5,51243535,51.244,7.987,6405442,ggml_vec_dot_q4_0_q8_0_nrc1
16,11008,512,5,102580175,102.580,15.988,6411261,ggml_vec_dot_q4_0_q8_0_nrc1
```

Trace:

```text
VERICURVE_TRACE,function=ggml_vec_dot_q4_0_q8_0,call_count=95232,last_n=11008,last_bs=0,last_nrc=1
```

## Interpretation

The old ggml-level path is essentially repeated T1:

```text
T=2  total_ratio=1.997
T=4  total_ratio=3.993
T=8  total_ratio=7.987
T=16 total_ratio=15.988
```

Per-token latency stays nearly constant at about:

```text
6.405 ms per T position for 512 rows and n=11008
```

This removes the main ambiguity from the model-level prompt-pass result:

```text
old prompt-pass near-linear
old current-path trace single-RHS nrc=1
old ggml-level qmatmul near-linear
```

The next required step is a harness-local T4 kernel with correctness against:

```text
4 x ggml_vec_dot_q4_0_q8_0
```

