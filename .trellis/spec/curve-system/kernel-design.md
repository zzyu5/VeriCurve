# T-Specialized RVV Verifier Kernel Design

T-specialized kernels are enabling artifacts. Their purpose is to reshape `C_verify(T)`, not to become the whole paper.

## First Target

Prefer the easiest low-bit path that can prove multi-RHS reuse:

```text
Q4_0 x Q8_0 verifier_T4
```

If llama.cpp's current RVV path makes another format much easier, document the reason before switching.

## Minimal T4 API Shape

The first implementation can be harness-local. It does not need to alter
llama.cpp ABI until correctness and curve shaping are proven.

```c
void q4_0_q8_0_dot_t4_rvv(
    int n,
    float out[4],
    const block_q4_0 * x,
    const block_q8_0 * y0,
    const block_q8_0 * y1,
    const block_q8_0 * y2,
    const block_q8_0 * y3
);
```

Correctness oracle:

```text
4 x existing ggml_vec_dot_q4_0_q8_0 on the same inputs
```

## Required Dataflow Difference

A T4 kernel must not be four independent T1 calls. The target dataflow is:

```text
for each K block:
  load/decode quantized weight block once
  load RHS activations x0, x1, x2, x3
  update acc0, acc1, acc2, acc3
reduce/store all accumulators
```

After a direct R1T4 failure, the next kernel must change more than the public
API shape. Valid post-direct designs include:

```text
RTile x TTile row-token blocking
packed or interleaved RHS layout
row-blocked or repacked weights
integration with existing llama.cpp 16x1 repack/GEMV/GEMM machinery
another quantization path with larger reusable work
```

The post-direct benchmark matrix should include at least:

```text
R1T1
R1T4
R2T2
R2T4
R4T1
R4T2
R4T4
```

If R4 is too complex for the first pass, R2T2 and R2T4 are the minimum useful
restart point.

## Current Post-Direct Evidence

On the current `rvv` host, a standalone Q4_0 x Q8_0 harness measured:

```text
old_t1 = 12.024 ms
old_t4 = 48.085 ms
direct R1T4 = previously NO-GO
row-blocked R8T4 total = 16.826 ms
row-blocked R8T4 / old_t4 = 0.350
row-blocked R8T4 / old_t1 = 1.399
correctness max_abs = 0
correctness max_rel = 0
```

This is a STRONG GO for layout-aware `RTile x TTile` curve shaping. The next
kernel path should start from row-blocked R8T4 on VLEN=128 RVV, then refine
integration and amortize weight repacking across real verifier calls.

## RVV Variables to Record

- SEW
- LMUL
- vsetvl placement
- unroll factor
- accumulator layout
- reduction timing
- weight unpack/dequant placement
- activation layout
- prefetch, if used
- thread partitioning

## Minimum Success Criteria

For T4:

```text
C_new(4) / C_new(1) <= 2.5: initially useful
C_new(4) / C_new(1) <= 2.0: strong
C_new(4) / C_new(1) > 3.5: pause and reassess
```

Against the old path:

```text
STRONG GO-system:
  C_new(4) <= 2.2 * C_old(1)
  and C_new(4) <= 0.60 * C_old(4)
  and correctness passes.

GO-system:
  C_new(4) <= 2.6 * C_old(1)
  and C_new(4) <= 0.70 * C_old(4)
  and correctness passes.

CONDITIONAL:
  C_new(4) <= 3.2 * C_old(1)
  or C_new(4) <= 0.85 * C_old(4).
  Allow one focused optimization pass, then reassess.

NO-GO for VeriCurve system:
  C_new(4) > 3.2 * C_old(1)
  and C_new(4) > 0.85 * C_old(4).
  Do not proceed to controller work.
```

## Failure Handling

If a correctness-passing minimal direct T4 kernel is slower than the old T4
path, do not reinterpret the result as a controller opportunity. The correct
action is:

```text
stop controller work
record NO-GO for the current minimal direct T4 system path
reopen only as a new kernel research task with a materially different design
```

Materially different designs include:

```text
RTile x TTile row-token blocking
repacked or interleaved RHS layout
row-blocked or repacked weights
integration with existing 16x1 repack machinery
scale-aware vector float accumulation
another quantization path with larger reusable work
```

A minor wrapper around four single-RHS calls, or a direct T4 kernel that still
pays four independent reduction paths without enough reuse, is not sufficient
to justify full-system continuation.

For T8:

```text
C_new(8) / C_new(1) <= 3.5: useful for high-acceptance workloads
T8 rebound/cliff: still useful if it motivates controller sweet-spot selection
```
