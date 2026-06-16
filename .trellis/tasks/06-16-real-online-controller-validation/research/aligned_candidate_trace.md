# Aligned Candidate Trace

Artifacts:

```text
patches/aligned_candidate_trace.patch
results/aligned_candidate_trace.csv
artifacts/aligned_candidate_*.csv
artifacts/aligned_candidate_*_commit_d3.csv
```

## Purpose

The previous trace had only `d=3` per-step data. `pro5.md` correctly identified
that this is insufficient for controller replay. The aligned trace records all
candidate outcomes from the same pseudo-output position:

```text
d in {0,1,3,7}
same chunk_id
same step_id
same pseudo_position
same ngram caches before commit
```

The committed trajectory still uses `--spec-draft-n-max 3`; candidate rows are
counterfactual measurements before the commit. This preserves one shared
pseudo-state sequence while exposing all candidate actions for replay.

## Patch

The patch adds:

```text
VERICURVE_LOOKUP_ALIGNED_TRACE_CSV=/path/to/out.csv
```

Output columns:

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

The existing `VERICURVE_LOOKUP_TRACE_CSV` remains available and records the
actual committed `d=3` path.

## Coverage

Aligned trace rows:

```text
chat_low:   653 steps x 4 candidates = 2612 rows
chat:       424 steps x 4 candidates = 1696 rows
code:       167 steps x 4 candidates = 668 rows
rag:        191 steps x 4 candidates = 764 rows
structured: 121 steps x 4 candidates = 484 rows
```

Total:

```text
1556 aligned steps
6224 candidate rows
```

## Reproduction Check

The aligned trace's `d=3` candidate exactly reproduces the committed d=3
aggregate from the previous per-step trace:

```text
chat:       171 drafted, 86 accepted, acceptance 0.502924
chat_low:   202 drafted, 112 accepted, acceptance 0.554455
code:       359 drafted, 345 accepted, acceptance 0.961003
rag:        389 drafted, 321 accepted, acceptance 0.825193
structured: 198 drafted, 135 accepted, acceptance 0.681818
```

This passes the pro5 reproduction gate.

## Decision

```text
Aligned candidate trace: GO
```

The trace is sufficient for offline aligned replay. It is still a controlled
lookup-stats trace, not a full target-decode runtime controller.
