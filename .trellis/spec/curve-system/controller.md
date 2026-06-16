# Curve-Aware Controller Contract

The controller chooses the draft budget `d`, not a generic kernel schedule.

## Objective

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
d* = argmin_d J(d)
```

Default candidates:

```text
d in {0,1,3,7,15}
T = 1 + d
```

## Minimal State

```c
struct vc_accept_stats {
    float ewma_accept_per_draft;
    float ewma_full_accept_rate;
    int window_tokens;
};
```

## Stability Rules

- Use a switch margin, default 5 percent predicted improvement.
- Update every 8 or 16 generated tokens, not every token.
- Use a minimum sample threshold before enabling adaptive switching.
- Keep fallback to `d=0` or existing llama.cpp behavior.

## Required Decision Log

Each decision should be loggable as:

```json
{
  "step": 128,
  "selected_d": 3,
  "selected_T": 4,
  "C_verify_ms": 190.0,
  "C_draft_ms": 0.1,
  "E_accept": 2.1,
  "score": 61.3,
  "actual_accept": 2,
  "fallback": false
}
```

Controller overhead must be measured or bounded.

## Entry Gate

Do not implement the controller before a minimal T-specialized kernel has
changed the verifier curve or before the project is explicitly downgraded to a
characterization-only controller study.

Controller work requires:

```text
C_new(T) for at least T in {1,4}, preferably {1,2,4,8}
C_draft(d) for d in {1,3,7,15}
acceptance(d) for at least two workloads with different behavior
```

Full-system Go/No-Go:

```text
FULL SYSTEM GO:
  VeriCurve-RV beats offline-best fixed d over a mixed workload by >= 10%,
  reaches >= 90% oracle,
  and has no major regression on low-acceptance workloads.

CONDITIONAL PAPER GO:
  VeriCurve-RV beats default/fixed policies but not offline-best fixed d.

NO-GO SYSTEM:
  offline-best fixed d matches oracle within 3-5%,
  or goodput-only adaptive matches VeriCurve-RV.
```

## Oracle Scoring Convention

For controller baselines, oracle must be scored as:

```text
total verifier+draft cost / total emitted tokens
```

Do not average per-position `cost / emitted_tokens` ratios and compare that
value against `J(d)`. `J(d)` is a total-cost-over-total-output statistic, and
mixing the two ratio definitions can make oracle appear worse than a policy it
should dominate.

## Current Feasibility Snapshot

Task:

```text
.trellis/tasks/06-16-curve-aware-controller-feasibility
```

Proxy result:

```text
B0 no speculation:             12.024 ms/token
B4 offline-best fixed mixed:    9.048 ms/token
B6 VeriCurve-RV offline:        8.226 ms/token
B7 per-position oracle:         7.190 ms/token
```

Gate status:

```text
CONDITIONAL PAPER GO, not FULL SYSTEM GO

passes:
  VeriCurve-RV offline beats offline-best fixed mixed by about 10.0%.
  Low-acceptance chat chooses d=0 and does not regress.
  Goodput-only adaptive is much worse, so cost-aware control matters.

fails:
  VeriCurve-RV offline reaches 87.4% oracle, below the strict 90% gate.
```

This snapshot uses deterministic ngram proxy acceptance. It is a controller
feasibility result, not a paper-grade end-to-end llama.cpp system result.

## Trace Requirements for Online Replay

Aggregate acceptance for `d in {1,3,7}` is not enough to claim an online
controller. It can estimate fixed-policy `J(d)`, but it cannot replay switching
or oracle behavior when different `d` values advance the pseudo output by
different accepted counts.

For online EWMA or oracle replay, collect one of:

```text
aligned per-step candidate traces for d in {0,1,3,7}
a real runtime choose_d loop that records decisions and outcomes
a deterministic trace generator that evaluates all candidate d from the same
pseudo position
```

Required per-step fields:

```text
workload
step_id
candidate_or_selected_d
drafted_count
accepted_count
estimated_E_accept
estimated_J
actual_J
switch_reason
```

Do not promote a result to full-system go if `d=3` is best for every measured
controlled workload and no online switching/oracle replay has been measured.

## Aligned Candidate Trace Contract

When aggregate d sweeps disagree with controller intuition, collect aligned
candidate rows from the same pseudo/runtime state before committing a step.

Environment variable for the llama.cpp lookup-stats prototype:

```text
VERICURVE_LOOKUP_ALIGNED_TRACE_CSV=/path/to/aligned.csv
```

Required columns:

```text
chunk_id
step_id
pseudo_position
candidate_d
drafted_count
accepted_count
target_available
trace_draft_us
```

Quality gate:

```text
GO:
  each workload has at least 100 aligned steps
  each aligned step has candidate_d in {0,1,3,7}
  d=3 candidate aggregate reproduces the committed d=3 trace within 5-10%

NO-GO:
  candidates are collected from separate pseudo trajectories and then compared
  as if they were same-state candidates
```

Current aligned replay snapshot:

```text
task: .trellis/tasks/06-16-real-online-controller-validation

fixed d=3:                       10.248 ms/token
best fixed per workload:          8.914 ms/token
VeriCurve EWMA full-info replay:  9.035 ms/token
oracle:                           7.666 ms/token
```

Interpretation:

```text
fixed d=3 is not close to oracle
chat/chat_low prefer d=0
code/rag/structured prefer d=3
EWMA full-info replay is promising but reaches only 84.9% oracle
```

This remains conditional evidence. It should not be described as a real online
controller until a selected-only replay or runtime `choose_d()` loop exists.

## Commit-Aware Replay Contract

### 1. Scope / Trigger

Use this contract when an aligned candidate trace is replayed as an online or
selected-only controller result.

Trigger:

```text
policy selects d at runtime/replay time
accepted_count(selected_d) changes the next pseudo position
```

### 2. Signatures

Replay input:

```text
aligned_candidate_trace.csv
```

Minimum command shape:

```text
python3 scripts/replay_policy_family.py \
  --aligned results/aligned_candidate_trace.csv \
  --verify <C_verify_best_curve.csv> \
  --out results
```

Required result files:

```text
results/replay_sanity_checks.csv
results/policy_family_replay.csv
```

### 3. Contracts

For every selected row:

```text
emitted_tokens = 1 + accepted_count(selected_d)
next_pseudo_position = current_pseudo_position + emitted_tokens
```

The replay must aggregate:

```text
sum(C_verify(1+d) + C_draft(d)) / sum(emitted_tokens)
```

It must not average per-step ratios.

Each replay row must state its mode:

```text
recorded_position_scan
commit_aware_available_trace
runtime_selected_path
```

Only `commit_aware_available_trace` with zero missing transitions or
`runtime_selected_path` may support selected-only controller claims.

### 4. Validation & Error Matrix

```text
missing next_pseudo_position for selected d
  -> mark insufficient_trace_coverage_for_selected_path
  -> do not compare ms/token as a valid full-sequence policy result

candidate set missing any d in {0,1,3,7}
  -> exclude that step from replay and report skipped count

oracle over recorded rows only
  -> label recorded_position_scan oracle, not commit-aware oracle

d=0 emitted_tokens != 1
  -> invalid replay input or parser bug
```

### 5. Good/Base/Bad Cases

Good:

```text
d=3 committed trace has missing_next_position = 0 and can replay fixed d=3
over all recorded positions.
```

Base:

```text
recorded_position_scan compares fixed policies, full-info EWMA, and scan oracle
as diagnostic upper-bound evidence only.
```

Bad:

```text
a policy chooses d=0 on a d=3 committed trace, hits missing next positions, and
the early-stopped ms/token is reported as a speedup.
```

### 6. Tests Required

Before promoting a selected-only policy:

```text
assert replay_sanity_checks.csv has missing_next_position = 0 for every
selected transition path being claimed

assert d=0 emitted_tokens_min = 1 and emitted_tokens_max = 1

assert fixed d=3 commit-aware replay reproduces the committed d=3 aggregate

assert policy_family_replay.csv includes mode and coverage_status columns
```

### 7. Wrong vs Correct

Wrong:

```text
Scan all rows from a d=3 committed aligned trace, choose d=0/d3 per row, and
claim the resulting cost is a selected-only online controller.
```

Correct:

```text
After choosing d, jump to current_pseudo_position + 1 + accepted_count(d).
If that position is absent, label the trace insufficient and collect a
position-complete trace or run a real runtime choose_d loop.
```

Current pro6 audit snapshot:

```text
task: .trellis/tasks/06-16-real-online-controller-validation

mixed d=0 missing next-position transitions: 402
mixed d=1 missing next-position transitions: 318
mixed d=3 missing next-position transitions: 0

selected_threshold_t0.4 scan-mode: 8.968 ms/token, 85.5% oracle
selected-only commit-aware claim: blocked by trace coverage
```

Current pro7 replay snapshot:

```text
task: .trellis/tasks/06-16-real-online-controller-validation

prefix-state equivalence: GO
position-complete candidate rows: 10200
position-complete positions: 2550
commit-aware replay missing transitions: 0

fixed d=3: 10.248 ms/token
best selected-only {0,3} threshold: 9.082 ms/token
commit-aware oracle: 8.090 ms/token
oracle reach: 89.1%
```

Interpretation:

```text
selected-only replay is no longer blocked by trace coverage
two-action threshold control beats fixed d=3 by about 11.4%
strict full-system gate remains open because oracle reach is below 90% and no
runtime choose_d loop has been measured
```
