# PRD: Post Direct T4 Go/No-Go

## Background

The direct R1T4 verifier microkernel experiment failed as a system path. It
passed correctness, but it was slower than four old single-RHS calls:

```text
old_t1 = 11.738 ms
old_t4 = 46.890 ms = 3.995 x old_t1
new_t4 = 79.464 ms = 6.770 x old_t1 = 1.695 x old_t4
```

This means visible `T` alone is not enough. VeriCurve-RV may continue only if a
materially different design can reshape `C_verify(T)`.

## Objective

Determine whether VeriCurve-RV should continue via one of these paths:

```text
A. layout-aware RTile x TTile curve-shaping verifier microkernels
B. schedule-variant crossover / runtime schedule selection
C. cache-aware characterization
D. controller work only after A or B succeeds
```

If A, B, and C all fail, stop this research line instead of building a
controller on a flat or worse verifier curve.

## Hard Rules

- Do not implement a speculation controller unless `A4` is GO/STRONG GO or
  `B2` is GO.
- Do not reinterpret the failed direct R1T4 result as a controller opportunity.
- Do not touch TianchenRV working trees or shared control/canary directories on
  `rvv`.
- Use isolated work under `~/vericurve-rv-lab/`, low priority commands, and
  single-thread or `-j1` builds unless the machine is clearly idle.
- Preserve raw command output, commit/hash, build flags, benchmark parameters,
  correctness metrics, and decision labels.

## Part A: Curve-Shaping Kernel Viability

### A0. Inherited Conclusion

Create `research/inherited_conclusion.md` with the direct R1T4 evidence and
the rule that the next kernel must materially differ through row blocking,
token blocking, RHS packing, weight repacking, or existing repack/GEMM
machinery.

### A1. Existing Repack / llamafile / tinyBLAS / 16x1 Audit

Audit the current llama.cpp tree used for RVV evidence:

```text
ggml/src/ggml-cpu/repack.cpp
ggml/src/ggml-cpu/arch/riscv/*
ggml/src/ggml-cpu/llamafile/*
ggml_compute_forward_mul_mat path
```

Required questions:

```text
Do q4_0_16x1_q8_0, q4_K_16x1_q8_K, or q8_0_16x1_q8_0 paths exist?
Do they support RVV?
What are their guard conditions?
Does current hardware satisfy VLEN, zvfh, shape alignment, quant type, and build flag guards?
Does the current T=4 prompt or microbench enter those paths?
If not, what is the reason: build flag, shape, layout, quant type, or call path?
```

Artifacts:

```text
research/repack_path_audit.md
results/repack_path_conditions.csv
patches/repack_trace.patch
```

Decision labels:

```text
GO-existing-repack:
  a suitable path exists but was not selected due to guard/config/shape, and
  can be safely forced in a microbenchmark.

GO-custom-RT-kernel:
  existing repack is unavailable or irrelevant for current Q4_0 x Q8_0 RVV,
  but the audit identifies a realistic custom RTile x TTile kernel path.

NO-GO-repack-branch:
  existing repack was already selected and still leaves the curve near-linear,
  or no relevant low-bit RVV path can be used for curve shaping.
```

### A2. RTile x TTile Microkernel Matrix

Build a standalone benchmark matrix:

```text
Rtile in {1,2,4,8}
Ttile in {1,2,4,8}
required cells: R1T1, R1T4, R2T2, R2T4, R4T1, R4T2, R4T4
```

If R4 is too complex, start with R2T2 and R2T4 but record the limitation.

Artifacts:

```text
scripts/bench_rtile_ttile_kernel.cpp
research/rtile_ttile_design.md
results/rtile_ttile_matrix.csv
patches/rtile_ttile_harness.patch
```

### A3. Layout Ablation

Measure at least these layout classes:

```text
Layout0: no packing
Layout1: packed RHS
Layout2: row-blocked weights
Layout3: packed RHS + row-blocked weights
```

Report separately:

```text
C_pack_rhs(T)
C_pack_weight_once
C_kernel
C_total
correctness max_abs and max_rel
```

Artifacts:

```text
research/layout_ablation.md
results/layout_ablation.csv
patches/layout_pack_harness.patch
```

### A4. Curve-Shaping Decision

Required summary columns:

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

Artifacts:

```text
research/curve_shaping_go_nogo.md
results/curve_shaping_summary.csv
```

## Part B: Schedule Variant Crossover

Construct variants such as current, small LMUL, large LMUL, deferred-wide
reduction, row-blocked, token-blocked, and row+token variants when available.

Measure:

```text
T(variant, B) for B/T in {1,2,4,8,16}
```

Artifacts:

```text
research/variant_space.md
results/variant_manifest.csv
results/variant_timing.csv
research/schedule_variant_go_nogo.md
```

Decision:

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

## Part C: Cache-Aware Characterization

Measure whether old verifier slope changes with model size, quantization, and
working-set scale.

Default matrix:

```text
model_size: synthetic, 1B, 3B, 7B when available
quant: Q4_0, Q4_K_M, Q5, Q8 when available
T: 1,2,4,8,16
threads: 1 first, 4 only if rvv is idle
```

Add perf/cache counters or a synthetic working-set sweep when hardware counter
access is unavailable.

Artifacts:

```text
results/cache_characterization.csv
research/cache_characterization.md
results/synthetic_workingset_sweep.csv
```

Decision:

```text
GO-cache-characterization:
  C(T) slope changes significantly with model/quant/working-set and correlates
  with counters or a synthetic cache cliff.

CONDITIONAL:
  slope changes weakly or lacks counter evidence.

NO-GO:
  curves stay near-linear across all available settings and no cache
  explanation is visible.
```

## Part D: Controller Readiness

Controller work is `READY` only if:

```text
A4 is GO or STRONG GO
or B2 is GO
```

Otherwise it is `NOT READY`. Do not run draft-cost or controller experiments
inside this task unless that prerequisite is satisfied.

## Final Required Output Template

```text
Final Go/No-Go Summary

A. Curve-shaping kernel:
  status: STRONG GO / GO / CONDITIONAL / NO-GO
  key evidence:
    C_old_T4 =
    C_best_T1 =
    C_candidate_T4_total =
    speedup_vs_old_T4 =
    curve_ratio =
  interpretation:

B. Schedule variant crossover:
  status: GO / CONDITIONAL / NO-GO
  key evidence:
    number_of_variants =
    best_static_latency =
    best_dynamic_latency =
    dynamic_gain =
    crossover_observed = yes/no
  interpretation:

C. Cache-aware characterization:
  status: GO / CONDITIONAL / NO-GO
  key evidence:
    slope_changes =
    cache_counter_correlation =
    synthetic_cache_cliff =
  interpretation:

D. Controller readiness:
  status: READY / NOT READY
  reason:

Recommended next research direction:
  1. Continue VeriCurve-RV system
  2. Pivot to Schedule-at-Inference-Time
  3. Pivot to cache/measurement paper
  4. Stop this line
```

## Completion Criteria

- Task artifacts for A0-A4 exist and support a curve-shaping status.
- B and C are either measured or explicitly scoped as blocked/deferred with a
  defensible reason and a clear impact on the final recommendation.
- The final summary uses the required template.
- Specs are updated with any reusable decisions or safety constraints learned
  from the task.
- `task.py validate` passes for the task.
