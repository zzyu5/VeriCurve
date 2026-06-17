# Real RVV T8 Policy Impact

Date: 2026-06-17 Asia/Shanghai

## Replay Curve

Replay used the committed rows512 verifier curve with only T8 replaced by the
best real RVV T8 measurement:

```text
T1 = 12.024 ms, old_vecdot_nrc1
T2 = 24.037 ms, old_vecdot_nrc1
T4 = 16.826 ms, R8_rowblocked_weights_total
T8 = 21.144 ms, real native_T8_packed_rhs_rowblocked_weights R16
```

This isolates the effect of the real T8 gate instead of changing the whole
controller evidence stack.

## Key Replay Results

```text
goodput-only adaptive:             9.160689 ms/token
existing selected-only curve-aware: 9.078115 ms/token
full-info myopic plan-aware:        7.492851 ms/token
two-action oracle {d0,d3}:          8.090088 ms/token
multi-action oracle {d0,d1,d3,d7}:  7.461463 ms/token
```

Multi-action oracle:

```text
choices: d0=1138; d3=153; d7=133
gain over {d0,d3}: 8.424949%
```

Full-info myopic plan-aware:

```text
choices: d0=1148; d3=164; d7=122
advantage vs goodput-only: 22.259059%
oracle reach vs multi-action oracle: 0.995811
```

Existing selected-only curve-aware:

```text
choices: d0=1274; d3=468
advantage vs goodput-only: 0.909599%
```

The existing selected-only policy still does not exploit d7 because its action
set is hard-coded to `{d0,d3}`. This is no longer a T8 verifier limitation; it
is now a controller design limitation.

## Gate Interpretation

Did multi-action policy become meaningful?

```text
YES
```

The real T8 plan makes d7 appear in both the multi-action oracle and the
full-info myopic plan-aware replay.

Did plan-aware beat goodput-only by at least 5%?

```text
YES for full-info myopic plan-aware replay.
NO for the existing selected-only two-action policy.
```

Therefore:

```text
A-level VeriCurve mechanism: GO at verifier-plan mechanism level.
Runtime controller contribution: still open / not yet selected-only proven.
```

The next falsifiable question is no longer "can RVV T8 reach the threshold?"
It is:

```text
Can a selected-only or low-observability controller recover enough of the
full-info plan-aware gain without oracle access?
```
