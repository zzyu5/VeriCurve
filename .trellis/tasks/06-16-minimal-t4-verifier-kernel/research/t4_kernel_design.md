# Minimal T4 Kernel Design

## Purpose

This design tests the smallest T4 idea for the traced current path:

```text
current path: ggml_vec_dot_q4_0_q8_0
current nrc: 1
old T4: 4 x old T1 vec-dot
new T4: one Q4_0 block decode feeding four Q8_0 RHS accumulations
```

It is a harness-local experiment, not a llama.cpp ABI change.

## API

```c
static void q4_0_q8_0_dot_t4_rvv(
    int n,
    float out[4],
    const block_q4_0 * x,
    const block_q8_0 * y0,
    const block_q8_0 * y1,
    const block_q8_0 * y2,
    const block_q8_0 * y3
);
```

Source:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/scripts/bench_t4_kernel.cpp
```

Patch artifact:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/patches/t4_kernel_minimal.patch
```

## Dataflow

For each Q4_0 block:

```text
load q4 packed bytes once
extract low/high nibbles once
subtract offset 8 once
for each of four Q8_0 RHS blocks:
  load two int8 halves
  vwmul/vwmacc with decoded q4 halves
  reduce int16 vector product to int32 scalar
  multiply by q4 scale and RHS scale
```

The design reuses Q4 load/decode across four RHS vectors but still performs one
horizontal reduction per RHS per block. This is intentionally minimal and
matches the first kernel-gate request. It does not implement a more invasive
packed/interleaved RHS layout or a scale-aware deferred reduction.

## Correctness Oracle

The oracle is:

```text
4 x ggml_vec_dot_q4_0_q8_0
```

The harness compares all four outputs for every tested row.

## Important Limitation

Q4_0 and Q8_0 scales vary per block, so a naive integer deferred reduction
across all blocks is not directly equivalent. A stronger T4 design would need a
different accumulation strategy, interleaved data layout, or scale-aware vector
float accumulation. This minimal kernel intentionally does not assume those.

