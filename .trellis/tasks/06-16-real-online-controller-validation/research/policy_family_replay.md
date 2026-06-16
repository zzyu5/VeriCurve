# Policy Family Replay

Artifacts:

```text
results/policy_family_replay.csv
scripts/replay_policy_family.py
```

Two replay modes are reported.

## Mode 1: recorded_position_scan

This mode scans the aligned rows recorded from the committed d=3 trajectory. It
is comparable to the previous aligned replay, but it is not commit-aware.

Best scan-mode rows:

```text
scan oracle:                    7.666 ms/token
workload-label upper bound:      8.914 ms/token
selected threshold t=0.4:        8.968 ms/token
selected threshold t=0.6:        9.009 ms/token
full-info EWMA d0,d3:            9.035 ms/token
fixed d=3:                      10.248 ms/token
```

Scan-mode implications:

```text
two-action d in {0,3} is enough for most of the practical gain
threshold policies can beat the previous full-info EWMA in scan mode
none of these scan-mode policies reaches 90% mixed oracle
```

The best selected-threshold scan row:

```text
policy: selected_threshold_t0.4
ms/token: 8.968
relative to fixed d=3: 0.875
oracle reach: 85.5%
choices: d0=1172,d3=384
```

This is promising but not sufficient for FULL SYSTEM GO because the replay mode
is not selected-path correct.

## Mode 2: commit_aware_available_trace

This mode advances by:

```text
next pseudo_position = current pseudo_position + 1 + accepted_count(selected_d)
```

When the next position is missing from the aligned trace, the chunk stops and
the row is marked:

```text
insufficient_trace_coverage_for_selected_path
```

Important rows:

```text
fixed d=3:
  10.248 ms/token
  steps evaluated: 1556
  missing transitions: 0
  status: commit_aware_available_trace

workload-label upper bound:
  6.866 ms/token
  steps evaluated: 620
  missing transitions: 5
  status: insufficient_trace_coverage_for_selected_path

selected threshold t=0.4:
  7.482 ms/token
  steps evaluated: 416
  missing transitions: 8
  status: insufficient_trace_coverage_for_selected_path
```

The low ms/token values with missing transitions are invalid as performance
claims. They stop early after falling off the recorded d=3 trajectory.

## Go/No-Go

```text
STRONG/GO selected-only policy: not reached
CONDITIONAL: yes, scan-mode selected policies beat fixed d=3
NO-GO: not supported, because fixed d=3 is not close to scan oracle
```

Current decision:

```text
selected-only replay is blocked by trace coverage, not by policy failure.
```

Next required evidence:

```text
collect a position-complete aligned trace, or run the selected policy online in
llama.cpp and log the committed decisions directly.
```
