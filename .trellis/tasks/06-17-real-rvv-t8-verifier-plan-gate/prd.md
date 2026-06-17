# PRD: Real RVV T8 Verifier Plan Gate

## Goal

Run a real RVV T8 verifier-plan gate. Do not write a paper. Do not conclude an
A-level No-Go using only existing replay data.

The previous A-level search result is provisional because it did not build and
measure a new optimized RVV T8 verifier plan. This task determines whether an
actual RVV T8 plan can make multi-point speculation meaningful enough for an
A-level VeriCurve mechanism claim.

## Context Facts

```text
old Q4_0 x Q8_0 llama.cpp/RVV path: repeated-T1-like
direct R1T4: No-Go
row-blocked R8T4: Strong Go
  C_old_T4 = 48.085 ms
  C_best_T1 = 12.024 ms
  C_candidate_T4_total = 16.826 ms
  speedup_vs_old_T4 = 2.858x
  curve_ratio = 1.399
current policy: collapses mostly to d={0,3}
current native T8 C8/C1 ~= 3.45
estimated two-T4 C8/C1 ~= 2.80
threshold sweep: multi-action/A-level VeriCurve may require real T8 C8/C1 <= 2.1
```

## Important Instructions

- Run a real RVV discriminating experiment unless remote safety check fails.
- If the experiment cannot be run safely, return `INCOMPLETE`, not `NO-GO`.
- Use only `~/vericurve-rv-lab/` on `rvv`.
- Do not use sudo, install packages, mutate system config, or touch TianchenRV trees.
- Use `nice -n 10`, `timeout`, and `threads=1`.
- If compile is needed, use `-j1` only.
- Do not update the project to Version B.
- Do not write paper framing.
- Do not do only replay analysis.
- Do not optimize R8T4 further unless it is required to construct a real T8 plan.

## Step 0: Remote Safety

Run lightweight checks:

```text
uptime
load average
memory
who
ps for llama/cmake/ninja/gcc/TianchenRV/Codex
```

Stop after read-only inspection if:

```text
machine is heavily loaded
active compile/model/TianchenRV/Codex jobs are visible
commands hang or show filesystem/kernel issues
the next step would need sudo, package install, or broad rebuild
```

Deliver:

```text
research/rvv_t8_safety_check.md
artifacts/rvv_t8_safety_check.txt
```

## Step 1: Audit Existing T8 Code Path

Inspect the current `bench_rtile_ttile_kernel` / R8T4 implementation and classify
the existing T8 route as one of:

```text
a) native R8T8
b) two T4 calls
c) extrapolated CSV estimate
d) repeated T1/T4 fallback
```

Deliver:

```text
research/t8_path_audit.md
```

## Step 2: Implement and Measure Real T8 Verifier Candidates

Implement the smallest real RVV/harness-level candidates. Correctness oracle:
8 x old T1 vecdot.

Candidate order:

```text
A. real composed T8 = two actual R8T4 calls in one measured harness path,
   including real loop overhead and any packing cost
B. native R8T8 no-pack verifier plan
C. R8T8 with packed RHS layout
D. R4T8 or R16T8 if R8T8 register pressure is clearly bad
E. one LMUL/unroll variant for the best candidate, if feasible
```

Do not stop after one failed candidate unless the failure explains all likely
T8 designs. Keep the scope narrow:

```text
quant/path: Q4_0 x Q8_0 first
rows: 512 first
threads: 1
```

Required metrics:

```text
correctness max_abs / max_rel vs 8 x old T1
C_best_T1
C_old_T8
C_candidate_T8
C_candidate_T8 / C_best_T1
speedup_vs_old_T8
packing cost separated from kernel cost if packing is used
```

Deliver:

```text
scripts/bench_t8_verifier_plan.cpp or patch to existing harness
results/real_rvv_t8_curve.csv
research/real_rvv_t8_gate.md
patches/t8_verifier_plan.patch
```

## Step 3: Rows Robustness

If the rows512 candidate reaches `C8/C1 <= 2.3`, also test one robustness case:

```text
rows2048
or alternate quant/path if rows2048 is too slow or not meaningful
```

Report:

```text
rows512 C8/C1
rows2048 or alternate C8/C1
whether degradation is fatal or explainable
```

## Step 4: Replay With Real T8

Use the newly measured real C_verify(T) curve for:

```text
T = 1, 2, 4, 8
```

Replay matrix:

```text
no speculation
fixed d=3
fixed d=7
best fixed per workload
workload-label upper bound
goodput-only adaptive
curve/plan-aware policy
oracle
```

Deliver:

```text
results/real_rvv_t8_replay_matrix.csv
research/real_rvv_t8_policy_impact.md
```

## Step 5: A-Level Go/No-Go Gates

`A-level GO` only if all are true:

```text
1. real rows512 T8 C8/C1 <= 2.1,
   or a clearly justified near-pass <= 2.3 with additional policy benefit
2. multi-action oracle over d={0,1,3,7} improves over {0,3} by >= 5%
3. curve/plan-aware policy beats goodput-only by >= 5%
4. the result does not collapse on rows2048 or the alternate robustness case
5. the conclusion is not explainable as "R8T4 is just a faster kernel"
```

`CONDITIONAL GO`:

```text
real T8 C8/C1 is 2.1 to 2.5 and reveals a plausible path,
but policy gain is <5%.
Recommend one more targeted kernel design step only if there is a clear bottleneck.
```

`NO-GO`:

```text
real T8 C8/C1 > 2.5 after reasonable native/composed attempts;
or T8 reaches <=2.1 but multi-action policy still does not beat {0,3};
or curve-aware policy is still tied with goodput-only.
```

`INCOMPLETE`:

```text
remote safety check fails;
remote tree lacks the required harness and building one would violate limits;
or the measurement cannot be run without sudo, package install, broad rebuild,
or touching non-task trees.
```

## Final Answer Format

```text
1. Did you run real RVV T8 experiments? YES/NO.
2. Best real T8 candidate and its C8/C1.
3. Did multi-action policy become meaningful? YES/NO.
4. Did plan-aware beat goodput-only by >=5%? YES/NO.
5. A-level VeriCurve mechanism: GO / CONDITIONAL / NO-GO / INCOMPLETE.
6. If NO-GO, state the exact falsified mechanism and recommended pivot.
```
