# Commit-Aware Replay

Artifacts:

```text
scripts/replay_commit_aware.py
results/commit_aware_replay_summary.csv
results/commit_aware_replay_by_workload.csv
results/commit_aware_selected_threshold_trace.csv
```

## Replay Semantics

Every policy uses the same transition rule:

```text
position = 1
while position <= max_position:
    d = policy(state)
    accepted = accepted_count[position, d]
    cost += C_verify(1+d) + C_draft(position, d)
    emitted += 1 + accepted
    position += 1 + accepted
```

All summary metrics use:

```text
sum(cost) / sum(emitted)
```

The commit-aware oracle is computed with Dinkelbach iteration and per-chunk
dynamic programming over the same skip semantics.

## Mixed Results

```text
oracle:                         8.090 ms/token
best selected-only threshold:    9.082 ms/token
workload-label upper bound:      9.155 ms/token
best fixed per workload:         9.155 ms/token
fixed d=3:                      10.248 ms/token
fixed d=0:                      12.024 ms/token
```

Best selected-only row:

```text
policy: selected_threshold_t0.4_p16
arms: d in {0,3}
threshold: 0.4
probe interval: 16
ms/token: 9.082
relative to fixed d=3: 0.886
oracle reach: 89.1%
choices: d0=1272,d3=470
missing transitions: 0
```

## Gate Check

Against fixed d=3:

```text
10.248 / 9.082 = 1.128
```

The selected-only policy beats fixed d=3 by about 11.4% cost reduction.

Against oracle:

```text
8.090 / 9.082 = 89.1%
```

This misses the strict 90% oracle gate by about 0.9 percentage points.

Low-acceptance regression against no speculation:

```text
chat:
  selected threshold: 12.217 ms/token
  fixed d=0:          12.024 ms/token
  regression:          1.6%

chat_low:
  selected threshold: 12.017 ms/token
  fixed d=0:          12.024 ms/token
  regression:         -0.1%
```

The low-acceptance regression gate passes under the 3% threshold.

## Decision

```text
commit-aware selected-only controller: CONDITIONAL / NEAR-GO
full system: not yet
```

The result is much stronger than scan-mode evidence because it is
position-complete and has zero missing transitions. It still should not be
called FULL SYSTEM GO because oracle reach is below 90% and this is replay, not
a runtime `choose_d()` integration.
