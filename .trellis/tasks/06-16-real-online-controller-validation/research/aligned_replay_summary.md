# Aligned Replay Summary

Artifacts:

```text
results/aligned_replay_summary.csv
results/aligned_replay_by_workload.csv
results/online_ewma_replay_trace.csv
scripts/replay_aligned_controller.py
```

## Scoring

All replay baselines use:

```text
total verifier+draft cost / total emitted tokens
```

Candidate cost:

```text
C_verify_best(1+d) + aligned trace draft_us
```

Candidate output:

```text
1 + accepted_count(d)
```

Oracle uses Dinkelbach-style fractional optimization so that it optimizes the
same total-cost-over-total-output objective as fixed policies.

pro6 audit caveat:

```text
This file reports recorded-position scan replay over the committed d=3
trajectory. It is not a commit-aware selected-path replay.
```

The follow-up audit is recorded in:

```text
research/replay_correctness_audit.md
results/replay_sanity_checks.csv
```

## Mixed Replay Results

```text
B0 no speculation:                  12.024 ms/token
B1 fixed d=1:                       19.044 ms/token
B2 fixed d=3:                       10.248 ms/token
B3 fixed d=7:                       19.100 ms/token
B4 best fixed mixed:                10.248 ms/token
B5 best fixed per workload:          8.914 ms/token
B6 goodput-only:                    19.100 ms/token
B7 VeriCurve EWMA full-info replay:  9.035 ms/token
B8 oracle:                           7.666 ms/token
```

Relative to fixed `d=3`:

```text
best fixed per workload: 0.870x cost
VeriCurve EWMA full-info: 0.882x cost
oracle: 0.748x cost
```

Oracle reach:

```text
fixed d=3: 74.8%
best fixed per workload: 86.0%
VeriCurve EWMA full-info: 84.9%
```

## Workload Findings

Aligned replay changes the earlier aggregate interpretation:

```text
chat:       fixed d=0 is better than fixed d=3
chat_low:   fixed d=0 is better than fixed d=3
code:       fixed d=3 is best among fixed policies
rag:        fixed d=3 is best among fixed policies
structured: fixed d=3 is best among fixed policies
```

This means the controller opportunity is real:

```text
low-acceptance workloads prefer no speculation
high-acceptance workloads prefer d=3
```

The previous aggregate sweep made `d=3` appear best everywhere because separate
`d` runs followed different pseudo-output trajectories. The aligned trace is the
more reliable controller replay input.

## Go/No-Go

Full-system gate from pro5:

```text
VeriCurve replay beats fixed d=3 by >= 8%
and reaches >= 90% oracle
and does not regress low-acceptance workload by >3%.
```

Observed:

```text
beats fixed d=3:
  10.247931 / 9.034761 = 1.134
  pass for the full-info replay upper bound

oracle reach:
  7.666012 / 9.034761 = 0.849
  fail strict >=90%

low-acceptance behavior:
  replay selects many d=0 actions in chat/chat_low
  directional pass, but this is still full-information replay
```

## Decision

```text
Aligned replay: CONDITIONAL GO
Full system: not yet
```

This is not a controller no-go:

```text
fixed d=3 is far from oracle, not within 3%
goodput-only is much worse because it always prefers d=7
aligned replay shows different best fixed d across workloads
```

But it is not full-system go:

```text
the EWMA replay is full-information and optimistic
the replay scans recorded d=3-trajectory positions
oracle reach is below 90%
there is no real selected-only online controller yet
```

Next step should be a selected-only controller or a real runtime `choose_d()`
loop over the aligned trace mechanics.
