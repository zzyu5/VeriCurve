# Controller E2E Summary

Artifacts:

```text
results/controller_e2e_summary.csv
results/aligned_replay_summary.csv
results/replay_sanity_checks.csv
results/policy_family_replay.csv
results/policy_train_test.csv
```

## Status

```text
FULL SYSTEM GO: no
Current status: CONDITIONAL
Online controller: BLOCKED_BY_TRACE_COVERAGE
```

## What Passed

Trace plumbing:

```text
VERICURVE_LOOKUP_TRACE_CSV produced 1556 per-step d=3 trace rows from
llama.cpp lookup-stats across chat_low, chat, code, rag, and structured.
```

Candidate-aligned trace:

```text
aligned_candidate_trace.csv has 6224 rows:
  1556 same-position steps x d in {0,1,3,7}
```

Committed d=3 reproduction:

```text
d=3 candidate rows reproduce the committed d=3 trace.
mixed d=3 missing next-position transitions: 0
```

Workload-dependent policy opportunity:

```text
chat/chat_low prefer d=0
code/rag/structured prefer d=3
```

This corrected the earlier aggregate-sweep misconception that fixed d=3 was
best everywhere.

## Strongest Current Numbers

Recorded-position scan mode:

```text
fixed d=3:                 10.248 ms/token
workload-label upper bound: 8.914 ms/token
full-info EWMA:             9.035 ms/token
scan oracle:                7.666 ms/token
```

Simple policy family:

```text
selected_threshold_t0.4 scan-mode:
  8.968 ms/token
  0.875x fixed d=3
  85.5% oracle reach
```

Train/test scan-mode:

```text
best train-ranked threshold policy:
  train relative to fixed d=3: 0.871
  test relative to fixed d=3:  0.916
  test oracle reach:          85.5%
```

## What Failed or Remains Missing

The previous aligned replay is not commit-aware:

```text
it scans recorded d=3-trajectory positions
it does not jump by 1 + accepted_count(selected_d)
```

The current aligned trace is not position-complete for non-d3 selected paths:

```text
mixed d=0 missing next-position transitions: 402
mixed d=1 missing next-position transitions: 318
```

Therefore:

```text
scan-mode selected policies are diagnostic only
early-stopped commit-aware rows with missing transitions are invalid as
full-sequence performance claims
no selected-only online controller has been proven
```

## Decision

```text
aligned candidate trace: GO
workload-dependent policy opportunity: GO
fixed d=3 close to oracle: NO
selected-only controller: NOT PROVEN
full system: NO
```

The next decisive step is not more scan-mode tuning. It is one of:

```text
1. collect a position-complete aligned trace, likely by committing d=0 and
   evaluating d in {0,1,3,7} at every position, or
2. run a real runtime choose_d policy and log selected decisions directly.
```
