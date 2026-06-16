# Online Controller Status

Artifacts:

```text
results/online_controller_trace.csv
results/online_controller_trace_summary.csv
results/controller_e2e_summary.csv
```

## What Exists

The task now has per-step d=3 trace from patched `llama-lookup-stats`:

```text
1556 trace rows across:
  chat_low
  chat
  code
  rag
  structured
```

This trace records:

```text
drafted_count
accepted_count
pseudo output position
draft/update timing delta
```

## Aligned Replay Update

The follow-up aligned trace now evaluates `d in {0,1,3,7}` from the same pseudo
positions. Results:

```text
fixed d=3:                       10.248 ms/token
best fixed per workload:          8.914 ms/token
VeriCurve EWMA full-info replay:  9.035 ms/token
oracle:                           7.666 ms/token
```

This proves the controller opportunity is real in replay:

```text
chat/chat_low prefer d=0
code/rag/structured prefer d=3
```

But the EWMA replay is still a full-information upper bound because it updates
all candidate EWMAs from the aligned trace after each step.

## What Is Missing

A real online EWMA controller is not implemented yet.

The next implementation needs one of:

```text
1. a selected-only replay policy with explicit exploration, or
2. a real runtime loop that chooses d online and records each decision.
```

The current aligned replay can score oracle and upper-bound EWMA, but it is not
yet deployable online-controller evidence.

## pro6 Replay Semantics Audit

`results/replay_sanity_checks.csv` shows that the previous aligned replay is a
recorded-position scan, not a selected-path replay. The d=3 committed trajectory
is complete:

```text
mixed d=3 missing next-position transitions: 0
```

But non-d3 selected paths are not position-complete:

```text
mixed d=0 missing next-position transitions: 402
mixed d=1 missing next-position transitions: 318
```

Therefore current selected-only controller evidence is blocked by trace
coverage. Scan-mode selected policies are promising but not final:

```text
selected threshold t=0.4 scan-mode: 8.968 ms/token
relative to fixed d=3: 0.875
oracle reach: 85.5%
```

Commit-aware replay over the available trace marks non-d3 policies as:

```text
insufficient_trace_coverage_for_selected_path
```

## Current Controller Implication

The result is not full-system go:

```text
EWMA full-info replay reaches only 84.9% oracle
no selected-only choose_d loop
no real target-decode online controller
non-d3 selected paths fall off the current d=3 committed aligned trace
```

## Decision

```text
Aligned replay: CONDITIONAL GO
Online controller: BLOCKED_BY_TRACE_COVERAGE
Current status: CONDITIONAL, not FULL SYSTEM GO
```

The next implementation step should be a position-complete aligned trace or a
small runtime `choose_d()` experiment, not further kernel tuning.
