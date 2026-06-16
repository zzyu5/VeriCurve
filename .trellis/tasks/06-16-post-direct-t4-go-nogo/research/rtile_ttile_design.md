# A2 RTile x TTile Microkernel Matrix

## Design

After the direct R1T4 failure, the harness changes the dataflow:

```text
for each row group R:
  for each K block:
    load T RHS q8 blocks
    for each row in R:
      load one q4 weight block
      update R x T accumulators
```

This differs from the failed direct R1T4 kernel in two ways:

```text
R reuse: the same RHS block is used across multiple weight rows.
T reuse: the same weight block is used across multiple RHS tokens.
```

The harness is intentionally standalone and links against the existing
`build-vericurve` ggml libraries. It does not alter llama.cpp runtime ABI.

Source:

```text
scripts/bench_rtile_ttile_kernel.cpp
```

Remote source path:

```text
/home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel.cpp
```

Compile:

```text
nice -n 10 timeout 180 g++ -std=c++17 -O3
  -march=rv64gcv_zfh_zvfh_zicbop_zihintpause -mabi=lp64d
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/include
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/src
  -I/home/ubuntu/vericurve-rv-lab/llama.cpp/ggml/src/ggml-cpu
  /home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel.cpp
  -L/home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve/bin
  -lggml-cpu -lggml-base -lggml
  -Wl,-rpath,/home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve/bin
  -o /home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel
```

Final run:

```text
nice -n 10 timeout 600
  /home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel
  11008 512 5 1
```

Parameters:

```text
n = 11008
rows = 512
repeats = 5
warmup = 1
threading = single-process harness
quant = Q4_0 x Q8_0
```

## Matrix Results

Canonical CSV:

```text
results/rtile_ttile_matrix.csv
```

Important rows:

```text
old_t1 = 12.024 ms
old_t4 = 48.085 ms

R1T4 no_pack = 41.465 ms = 0.862 x old_t4
R2T4 no_pack = 35.202 ms = 0.732 x old_t4
R4T4 no_pack = 31.586 ms = 0.657 x old_t4
R8T4 no_pack = 30.094 ms = 0.626 x old_t4

R8T8 no_pack = 41.537 ms = 0.431 x old_t8 estimate
```

Correctness:

```text
max_abs = 0
max_rel = 0
```

## Interpretation

The matrix shows that RTile matters. The failed direct R1T4 path was still
dominated by repeated RHS work and reduction overhead. Once rows are grouped,
the same RHS blocks are reused across multiple q4 rows, and T4 drops below the
old T4 path even without explicit packing.

The best no-pack T4 cell is:

```text
R8T4 no_pack = 30.094 ms
```

That is already a meaningful curve-shaping result:

```text
R8T4 no_pack / old_t4 = 0.626
R8T4 no_pack / old_t1 = 2.503
```

This is the first positive evidence that VeriCurve-RV should continue through a
layout-aware RTile x TTile verifier kernel, not through the previous direct
R1T4 design.
