# Position-Complete Candidate Trace

Artifacts:

```text
patches/position_complete_trace.patch
scripts/make_position_complete_trace_patch.py
results/position_complete_candidate_trace.csv
results/position_complete_trace_quality.csv
artifacts/position_complete_*.csv
```

## Method

`VERICURVE_LOOKUP_POSITION_COMPLETE_CSV` adds a disabled-by-default
teacher-forced trace hook.

For every target prefix position:

```text
construct pseudo state from target prefix tokens[0:position]
evaluate candidate d in {0,1,3,7}
record drafted_count and accepted_count
advance teacher-forced prefix by one target token
```

This generates a position-complete candidate table. Any selected policy can now
advance with:

```text
next_position = position + 1 + accepted_count(selected_d)
```

without falling off the trace.

## Trace Columns

```text
workload
chunk_id
position
candidate_d
drafted_count
accepted_count
target_available
pseudo_state_hash
recent_tokens_hash
context_hash
context_ngrams
context_edges
context_count_sum
draft_update_us
```

## Quality

```text
chat:       510 positions, 2040 rows, incomplete positions 0
chat_low:   765 positions, 3060 rows, incomplete positions 0
code:       510 positions, 2040 rows, incomplete positions 0
rag:        510 positions, 2040 rows, incomplete positions 0
structured: 255 positions, 1020 rows, incomplete positions 0
```

Total:

```text
2550 positions
10200 candidate rows
```

Every measured position has candidates for:

```text
d in {0,1,3,7}
```

## Decision

```text
position-complete trace: GO
```

This resolves the trace coverage blocker found in `research/replay_correctness_audit.md`.
