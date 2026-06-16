# Minimal T4 Verifier Kernel Go/No-Go

## Objective

Decide whether a T-specialized RVV verifier microkernel can reshape
`C_verify(T)` enough to justify continuing VeriCurve-RV as a full system
project.

This task follows the previous Go/No-Go task:

```text
.trellis/tasks/06-16-go-nogo-llamacpp-rvv-verifier-curve
```

Previous result:

```text
GO-kernel-gap
GO-minimal-T4-kernel
CONDITIONAL-controller
CONDITIONAL-full-system
```

Previous evidence:

```text
C_old_prompt_T on ssh rvv, Q4_0, threads=1:
  T=1  ratio=1.000
  T=2  ratio=1.965
  T=4  ratio=3.926
  T=8  ratio=7.753
  T=16 ratio=15.561
```

Interpretation:

```text
Current old path is repeated-T1-like at model prompt-pass level.
This proves a kernel-gap signal, not full VeriCurve-RV system success.
This task must prove or refute C_new(4) curve shaping.
```

## Sources of Truth

- `doc/pro.md`
- `.trellis/spec/project/positioning.md`
- `.trellis/spec/project/scope.md`
- `.trellis/spec/project/paper-claims.md`
- `.trellis/spec/llamacpp-rvv/current-path-audit.md`
- `.trellis/spec/llamacpp-rvv/remote-rvv-safety.md`
- `.trellis/spec/curve-system/profiler.md`
- `.trellis/spec/curve-system/kernel-design.md`
- `.trellis/spec/curve-system/controller.md`
- `.trellis/spec/experiments/go-nogo.md`
- `.trellis/spec/experiments/artifacts.md`
- Previous task evidence under `.trellis/tasks/06-16-go-nogo-llamacpp-rvv-verifier-curve/research/`

## Non-Negotiable Direction

Do not begin with:

```text
broad scheduler
profile-driven general framework
agent controller
general llama.cpp runtime rewrite
```

The next evidence must be:

```text
trace current path -> ggml-level C_old(T) -> minimal T4 microkernel
```

Controller work is out of scope until `C_new(T)`, `C_draft(d)`, and acceptance
create a non-trivial draft-budget decision.

## Remote Safety

The shared `rvv` host may be used, but must remain low disturbance:

- Always run read-only preflight before build or benchmark.
- Use `nice -n 10`.
- Use `timeout`.
- Default to `-j1`.
- Prefer longer timeout over higher parallelism. The previous 600-second build
  window was too short for a full fresh llama.cpp target on `-j1`; this task may
  use 1800-3600 seconds for a single low-priority build if the machine is idle.
- Do not use `sudo`.
- Do not install packages.
- Do not run stress tests.
- Do not write inside TianchenRV working trees.
- Do not mutate control/canary/instrumented llama.cpp trees unless explicitly
  requested.

## Task 1: Trace Current llama.cpp/RVV Path

Question:

```text
For T=1,2,4,8, what kernel path does real llama.cpp/RVV use?
```

Must distinguish:

```text
ggml_vec_dot_*_q8_*       single-RHS vec-dot path
ggml_gemv_*_16x1_*        RISC-V repack GEMV path
ggml_gemm_*_16x1_*        RISC-V repack GEMM path
llamafile / tinyBLAS      non-target path for this RVV evidence
scalar/fallback           fallback path
```

Preferred trace mode:

```text
GGML_VERICURVE_TRACE=1
```

Trace output must aggregate counts rather than printing inside hot loops:

```text
function_name
call_count
n / nr / nc / nrc / bs
T or token_width if available
total_time_ns if cheap
```

Artifacts:

```text
research/current_path_trace_T1_T2_T4_T8.md
artifacts/current_path_trace.csv
patches/current_path_trace.patch
```

Task 1 decision:

```text
GO-T4-kernel:
  T>1 q4/q8 low-bit call_count scales approximately with T,
  or trace shows nrc==1 / single-RHS vec-dot dominates.

CONDITIONAL:
  trace enters repack/GEMM path, but C_old(T) remains near-linear.
  Continue to ggml-level C_old(T) before implementing T4.

NO-GO for T4 kernel:
  trace shows current efficient multi-RHS low-bit GEMM,
  and microbenchmark C_old(4) < 2.2 * C_old(1).
```

## Task 2: ggml-Level C_old(T) Microbenchmark

Do not rely only on full `llama-bench` prompt-pass. Build or reuse a smaller
harness:

```text
bench_qmatmul_T.cpp
```

It should directly measure the low-bit qmatmul / dot path:

```text
T = 1,2,4,8,16
quant = Q4_0 x Q8_0 first
threads = 1
same model-like hidden size / row count
warmup + repeat
trace path recorded
```

Outputs:

```text
C_old_qmatmul(T)
C_old_qmatmul(T) / C_old_qmatmul(1)
per_token_latency
trace path
```

Artifacts:

```text
research/C_old_qmatmul_T_threads1.md
artifacts/C_old_qmatmul_T_threads1.csv
patches/bench_qmatmul_T.patch
```

Task 2 decision:

```text
GO-T4-kernel:
  C_old_qmatmul(4) >= 3.4 * C_old_qmatmul(1)

CONDITIONAL:
  2.4 * C_old(1) <= C_old(4) < 3.4 * C_old(1)

NO-GO for low-bit T4 gap:
  C_old(4) < 2.2 * C_old(1)
```

## Task 3: Minimal T4 Verifier Microkernel

First target:

```text
Q4_0 x Q8_0
```

Minimal dataflow:

```text
one weight row/block
four RHS activation vectors
four accumulators
weight block load/decode once
output four scalar results
```

Harness-level API is sufficient:

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
4 x existing ggml_vec_dot_q4_0_q8_0
```

Performance comparisons:

```text
C_new_t4
vs C_old_t4 = 4 x existing T1 path
vs C_old_qmatmul(4)
vs C_old_prompt_T4 if applicable
```

Artifacts:

```text
research/t4_kernel_design.md
research/C_new_T4_microbench.md
artifacts/C_new_T4_microbench.csv
patches/t4_kernel_minimal.patch
```

Task 3 decision:

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

## Out of Scope

- Full controller implementation.
- `C_draft(d)` and acceptance benchmarks before Task 3 reaches at least GO.
- Full TianchenRV integration.
- Broad llama.cpp ABI rewrite.
- Multi-thread scaling beyond `threads=1`.
- High-parallelism remote builds.

## Acceptance Criteria

- pro guidance has been summarized into this task and project specs.
- Current path trace is recorded or a concrete blocker is recorded.
- ggml-level old-curve measurement is recorded or a concrete blocker is
  recorded.
- Minimal T4 implementation is either measured with correctness/performance
  evidence, or explicitly rejected by Task 1/Task 2 No-Go evidence.
- A final label is written:

```text
STRONG GO-system
GO-system
CONDITIONAL
NO-GO for VeriCurve system
or INSUFFICIENT-EVIDENCE with exact blocker
```

