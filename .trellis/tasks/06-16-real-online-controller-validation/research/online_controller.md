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

A real runtime online controller is not implemented yet.

The next implementation needs one of:

```text
1. a real runtime loop that chooses d online and records each decision, or
2. a narrow tuning pass over the position-complete replay to close the last
   oracle gap before runtime integration.
```

The current position-complete replay can score selected-only policies with true
commit semantics, but it is still replay evidence rather than runtime
`choose_d()` evidence.

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

Therefore the pro6 selected-only controller evidence was blocked by trace
coverage. Scan-mode selected policies were promising but not final:

```text
selected threshold t=0.4 scan-mode: 8.968 ms/token
relative to fixed d=3: 0.875
oracle reach: 85.5%
```

Commit-aware replay over the available trace marks non-d3 policies as:

```text
insufficient_trace_coverage_for_selected_path
```

## pro7 Position-Complete Replay

The pro7 follow-up resolved the replay coverage blocker:

```text
prefix-state equivalence: GO
position-complete candidate trace: GO
commit-aware replay missing transitions: 0
```

Best selected-only two-action policy:

```text
selected_threshold_t0.4_p16:
  arms: d in {0,3}
  ms/token: 9.082
  relative to fixed d=3: 0.886
  oracle reach: 89.1%
```

Low-acceptance regression against no-spec:

```text
chat:     +1.6%
chat_low: -0.1%
```

## Current Controller Implication

The result is not full-system go:

```text
EWMA full-info replay reaches only 84.9% oracle
selected-only commit-aware replay reaches 89.1% oracle, below 90%
no real target-decode online controller
no runtime choose_d loop
```

## Decision

```text
Aligned replay: CONDITIONAL GO
Selected-only commit-aware replay: CONDITIONAL / NEAR-GO
Runtime online controller: NOT DONE
Current status: CONDITIONAL, not FULL SYSTEM GO
```

The next implementation step should be either a small runtime `choose_d()`
experiment for the `{0,3}` threshold policy or a narrow replay tuning pass to
close the final oracle gap. It should not be further kernel tuning.
