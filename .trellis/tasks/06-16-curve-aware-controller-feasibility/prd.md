# PRD: Curve-Aware Controller Feasibility

## Background

The `post-direct-t4-go-nogo` task changed the project status:

```text
direct R1T4: NO-GO
row-blocked R8T4 / layout-aware RTile x TTile: STRONG GO
schedule variant crossover: GO
cache characterization: CONDITIONAL/supporting
controller readiness: READY
```

Measured key result:

```text
C_old_T4 = 48.085 ms
C_best_T1 = 12.024 ms
C_candidate_T4_total = 16.826 ms
speedup_vs_old_T4 = 2.858 x
curve_ratio = 1.399
```

This task must not continue kernel-feasibility work as the main question. It
must determine whether the shaped verifier curve creates real speculation
budget choices and controller value.

## Objective

Determine whether the row-blocked R8T4 verifier curve can support a VeriCurve-RV
controller that improves over fixed draft budgets and strong baselines.

Core formula:

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

Candidate values:

```text
d in {0,1,3,7,15}
T = 1 + d in {1,2,4,8,16}
```

## Hard Rules

- Do not spend this task proving kernel feasibility again.
- Use the row-blocked `RTile x TTile` curve as the new verifier path.
- Keep runtime dispatch as a mechanism, not the paper's main contribution.
- Keep cache characterization as supporting evidence unless a much stronger
  multi-model/perf-counter result appears.
- Use cheap draft sources first; do not download or run large draft models
  unless the cheap-draft path is insufficient and the remote is idle.
- On `rvv`, use only isolated paths under `~/vericurve-rv-lab/`, low priority
  commands, timeouts, and no high-parallel builds.

## Task 1: C_verify_best(T)

Generate a verifier curve table for:

```text
T in {1,2,4,8,16}
variants:
  old vecdot
  RTile x TTile candidate
  best dynamic variant
```

Required columns:

```text
T
C_verify_old_ns
C_verify_old_ms
C_verify_new_ns
C_verify_new_ms
C_verify_best_ns
C_verify_best_ms
winner_variant
ratio_best_vs_T1
```

Artifacts:

```text
results/C_verify_best_curve.csv
research/C_verify_best_curve.md
```

Decision:

```text
GO:
  C_best(4) / C_best(1) <= 1.8
  and at least one crossover T exists.

CONDITIONAL:
  C_best(4) / C_best(1) <= 2.5

NO-GO:
  C_best(4) / C_best(1) > 3.0
```

## Task 2: C_draft(d)

Measure or model cheap draft cost for:

```text
draft sources:
  ngram-simple
  ngram-map
  ngram-mod
d in {1,3,7,15}
```

Required columns:

```text
draft_source
d
C_draft_ns
C_draft_ms
method
notes
```

Artifacts:

```text
results/C_draft.csv
research/C_draft.md
```

Question:

```text
Does CPU/RVV draft cost eat the R8T4 verifier-curve gain?
```

## Task 3: acceptance(d)

Workload buckets:

```text
chat
code
rag
structured
```

Preferred additional bucket:

```text
mixed
```

Record:

```text
workload
draft_source
d
E_accept
acceptance_per_draft
full_accept_rate
distribution / histogram notes
method
```

Artifacts:

```text
results/acceptance_by_workload.csv
research/acceptance_by_workload.md
```

Decision:

```text
GO:
  at least two workloads have different optimal d,
  at least one workload chooses d=3 or d=7,
  and at least one low-acceptance workload chooses d=0 or d=1.

NO-GO:
  all workloads choose the same d,
  or all d>0 are unprofitable.
```

## Task 4: Offline J(d)

Compute:

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

For each workload output:

```text
best_d_old_curve
best_d_new_curve
best_d_oracle
predicted_speedup_vs_no_spec
predicted_speedup_vs_fixed_d
```

Artifacts:

```text
results/Jd_offline_prediction.csv
research/Jd_offline_prediction.md
```

Expected useful pattern:

```text
old_curve: best_d is often 0/1
new_curve: high-acceptance workloads move to d=3 or d=7
low-acceptance workloads remain d=0 or d=1
```

## Task 5: Minimal Controller Go/No-Go

Do not implement a broad llama.cpp rewrite in the first pass. A minimal
controller can be evaluated offline first:

```text
profile table:
  C_verify(T)
  C_draft(d)

runtime state:
  recent E_accept(d)
  update every 8 or 16 generated tokens
  choose d in {0,1,3,7}
```

Baselines:

```text
B0 no speculation
B1 llama.cpp fixed default
B2 fixed d=3
B3 offline-best fixed d per workload
B4 offline-best fixed d over mixed workload
B5 goodput-only adaptive
B6 VeriCurve-RV
B7 oracle
```

Decision:

```text
FULL SYSTEM GO:
  VeriCurve-RV beats offline-best fixed d over mixed workload by >= 8-10%,
  reaches >= 90% oracle,
  and has no regression on low-acceptance workload.

CONDITIONAL PAPER GO:
  VeriCurve-RV beats default/fixed,
  but not offline-best fixed d.

NO-GO controller:
  offline-best fixed d or goodput-only adaptive matches within 3-5%.
```

Artifacts:

```text
results/controller_go_nogo.csv
research/controller_go_nogo.md
```

## Completion Criteria

- `C_verify_best_curve.csv` exists and classifies the verifier curve.
- `C_draft.csv` exists for cheap draft sources.
- `acceptance_by_workload.csv` exists for at least four workload buckets.
- `Jd_offline_prediction.csv` exists and reports old/new/fixed/oracle behavior.
- `controller_go_nogo.md` states FULL SYSTEM GO / CONDITIONAL PAPER GO /
  NO-GO controller using the criteria above.
- Trellis context validates.
- Any reusable controller/profiler lessons are written back to spec.
