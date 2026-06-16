# Go/No-Go Plan

Before committing to the full system, run the Go/No-Go sequence.

## Experiment 0: Current llama.cpp/RVV Path

Questions:

```text
Does current T>1 verification already use an efficient multi-RHS path?
Does it behave like repeated T1 work?
Which low-bit formats are easiest to measure and modify?
```

Outputs:

```text
notes/current_llamacpp_rvv_path.md
artifacts/call_trace_T1.txt
artifacts/call_trace_T4.txt
```

## Experiment 1: C_old(T)

Measure:

```text
T = 1,2,4,8,16
threads = 1 first, then 4 only if remote machine is idle
quant = at least one feasible low-bit format
```

Outputs:

```text
results/C_old_verify.csv
figures/C_old_curve.png
```

Prompt-pass timing is an acceptable first proxy for `C_old(T)` when full
speculative tracing is not ready, but it must preserve model, quantization,
thread count, backend flags, and raw llama.cpp output. It can advance the
project only to a kernel experiment, not to a full-system speedup claim.

First-pass decision heuristic:

```text
GO to Experiment 2:
  total_ratio(T=4) >= 3.5 and total_ratio(T=8) >= 7.0,
  with per-token improvement below 15%.

CONDITIONAL / trace first:
  current path may already have meaningful T amortization,
  or source path classification is inconsistent with timing.

NO-GO for kernel gap:
  current path is already close to the T-specialized target,
  for example C_old(4) / C_old(1) <= 2.5 without obvious trace artifacts.
```

These thresholds are not paper claims. They are engineering gates for whether
to spend the next task on a T4 kernel, more path tracing, or a fallback
characterization study.

## Experiment 2: Minimal T4 Kernel

Goal:

```text
Show that C_verify(T) can be reshaped by T-specialized dataflow.
```

Decision:

```text
GO strong: C_new(4) / C_new(1) <= 2.0
GO: C_new(4) / C_new(1) <= 2.5
weak/conditional: old path already strong, or T4 only slightly improves
NO-GO for system speedup: C_new(4) remains near 4x T1 and no curve drift is visible
```

Before Experiment 2 implementation, run two narrower gates:

```text
Trace gate:
  identify whether T>1 uses single-RHS vec_dot, repack GEMV/GEMM,
  llamafile/tinyBLAS, scalar fallback, or an unresolved route.

ggml-level old-curve gate:
  measure C_old_qmatmul(T) below full prompt-pass level and classify whether
  C_old_qmatmul(4) is GO, CONDITIONAL, or NO-GO for a T4 gap.
```

## Experiment 3: Draft Cost and Acceptance

Run this only after a reshaped verifier curve or a real schedule-variant
crossover exists. A direct R1T4 failure is not enough evidence to start
controller work.

Measure:

```text
C_draft(d), d = 1,3,7,15
accepted tokens
full accept rate
workload drift
```

If draft model cost dominates, report it as a result and focus on ngram or lower-cost draft sources.

## Direction Labels

Use these final labels:

- `GO-strong`: sweet spot or rebound in T in `{2,4,8}`, plus controller opportunity.
- `GO-characterization`: curves drift across quantization/hardware/workload even if single-curve sweet spot is weak.
- `CONDITIONAL`: current path already strong or kernel work is hard, but curve/controller paper may survive.
- `NO-GO`: curves are near-linear, T-specialized kernel cannot compress cost, draft cost is too high, and fixed d stays near oracle.

## Post-Direct-T4 Go/No-Go

When direct R1T4 fails, use a three-branch decision tree before continuing the
project.

### Branch A: Curve-Shaping Kernel

Audit existing repack/GEMV/GEMM paths first, then test an `RTile x TTile`
matrix and layout ablations.

Required summary:

```text
C_old_T1
C_old_T4
C_best_T1
C_candidate_T4_no_pack
C_candidate_T4_with_pack
C_candidate_T4_total
speedup_vs_old_T4
curve_ratio = C_candidate_T4_total / C_best_T1
correctness_max_abs
correctness_max_rel
```

Decision:

```text
STRONG GO:
  C_candidate_T4_total / C_best_T1 <= 2.5
  and C_candidate_T4_total <= 0.65 x C_old_T4

GO:
  C_candidate_T4_total / C_best_T1 <= 3.0
  and C_candidate_T4_total <= 0.75 x C_old_T4

CONDITIONAL:
  C_candidate_T4_total / C_best_T1 <= 3.4
  or C_candidate_T4_total <= 0.85 x C_old_T4

NO-GO:
  C_candidate_T4_total / C_best_T1 > 3.4
  and C_candidate_T4_total > 0.85 x C_old_T4
```

### Branch B: Schedule Variant Crossover

Use this branch only for actual variant timing, not for a broad controller.

```text
GO-runtime-variant:
  at least two variants are best for different T buckets,
  margin >= 7% in at least two buckets,
  and best-dynamic beats best-static by >= 8%.

CONDITIONAL:
  crossover exists but margin < 7%,
  or best-dynamic beats static by 3% to 8%.

NO-GO:
  one variant is within 3% of best across all T,
  or dynamic selection improves by < 3%.
```

### Branch C: Cache-Aware Characterization

Use cross-model, cross-quantization, or synthetic working-set sweeps to decide
whether a characterization paper remains.

```text
GO-cache-characterization:
  C(T) slope changes significantly with model/quant/working-set and correlates
  with counters or a synthetic cache cliff.

CONDITIONAL:
  slope changes weakly or lacks counter evidence.

NO-GO:
  curves stay near-linear across available settings and no cache explanation
  is visible.
```

### Controller Readiness

```text
READY:
  A is GO/STRONG GO or B is GO.

NOT READY:
  no C_new(T), no variant crossover, or only characterization evidence exists.
```

## Current Post-Direct Decision

The `post-direct-t4-go-nogo` task measured:

```text
A curve-shaping kernel: STRONG GO
  best candidate: row-blocked R8T4
  C_candidate_T4_total / C_best_T1 = 1.399
  C_candidate_T4_total / C_old_T4 = 0.350

B schedule variant crossover: GO
  old vec-dot is best for T=1/2
  R8 no-pack is best for T=4/8
  dynamic gain over best static = 8.896%

C cache characterization: CONDITIONAL
  synthetic working-set change appears at rows=2048, T=16
  no perf counters or multi-quant/model sweep yet

D controller readiness: READY
```

Recommended direction from this evidence is to continue VeriCurve-RV through
the row-blocked `RTile x TTile` verifier path, with runtime variant selection
as a secondary mechanism.

Current post-Experiment-1 labels may be more specific:

```text
GO-kernel-gap:
  old model-level or ggml-level C_old(T) is near-linear enough to justify T4.

GO-minimal-T4-kernel:
  trace and/or ggml-level C_old(T) leave room for a T4 kernel.

CONDITIONAL-controller:
  do not build the controller until C_new(T), C_draft(d), and acceptance make
  a non-trivial draft-budget choice visible.

CONDITIONAL-full-system:
  the paper system remains conditional until C_new(T), draft cost, acceptance,
  and end-to-end mixed-workload evidence exist.
```
