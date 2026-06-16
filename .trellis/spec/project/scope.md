# Scope and Deliverables

## Minimal Single-Paper Scope

The minimum publishable VeriCurve-RV prototype should include:

1. `C_verify(T)` and `C_draft(d)` profiler for llama.cpp/RVV.
2. Current llama.cpp/RVV verifier-path audit for T in `{1,2,4,8,16}`.
3. One curve-shaping verifier kernel, preferably T4 first, but only if it
   materially differs from repeated single-RHS work.
4. A curve-aware controller using:

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

5. Mixed workload benchmark against fixed-d and oracle baselines.

## Candidate Values

Use these default candidate sets unless a task explicitly changes them:

```text
d in {0, 1, 3, 7, 15}
T in {1, 2, 4, 8, 16}
```

## Preferred Engineering Path

- Start with current llama.cpp/RVV behavior and microbenchmarks.
- Prefer a standalone profiler/harness before invasive llama.cpp runtime changes.
- Prefer Q4_0 x Q8_0 or the easiest current llama.cpp low-bit path for the first kernel.
- Keep the first RVV kernel hand-written or TianchenRV-assisted, but do not make the paper depend on full generation.

## Stage Gates

Proceed in this order:

```text
Gate 1: current-path trace
  Identify the T=1/2/4/8 kernel route before claiming a kernel gap.

Gate 2: ggml-level C_old(T)
  Reproduce the old near-linear curve below full model prompt-pass level.

Gate 3: minimal T4 kernel
  Prove or refute C_new(4) curve shaping before controller work.

Gate 3b: post-direct-T4 branch
  If a direct R1T4 kernel passes correctness but is slower than the old T4
  path, do not continue directly to controller work. Reopen only through:
    A. layout-aware RTile x TTile kernels,
    B. schedule-variant crossover,
    C. cache-aware characterization,
    or stop.

Gate 4: C_draft and acceptance
  Measure draft cost and workload acceptance only after the kernel gap is
  proven or downgraded.

Gate 5: minimal controller
  Implement J(d)-based selection only if C_new(T), C_draft(d), and acceptance
  create a non-trivial decision.
```

If Gate 3 fails, do not keep building a controller. Reclassify the project as
kernel characterization, low-bit microkernel work, schedule-at-inference-time,
cache characterization, or No-Go for the full VeriCurve-RV system.

After a direct R1T4 failure, controller work is allowed only if:

```text
A4 curve-shaping status is GO or STRONG GO
or B2 schedule-variant status is GO
```

Otherwise report `Controller readiness: NOT READY`.

## Explicit Non-Goals for the First Paper

- Full TianchenRV integration.
- Hot-path JIT.
- Agent-based optimization.
- Multi-framework runtime.
- Complex tree speculative decoding.
- Formal verification.
- Large kernel marketplace or broad autotuning infrastructure.

## Fallback Boundaries

If T-specialized kernels are not strong enough, the project may fall back to a characterization/design-study paper. Do not hide this as a system speedup claim.

If draft-model cost dominates on CPU/RVV, focus on ngram/self-speculative mechanisms and report draft cost as a first-class result.
