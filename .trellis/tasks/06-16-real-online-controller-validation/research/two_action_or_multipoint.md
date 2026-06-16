# Two-Action or Multi-Point Controller

Date: 2026-06-17 Asia/Shanghai

Inputs:

- `results/position_complete_candidate_trace.csv`
- `../06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv`
- `scripts/resolve_claude_critique.py`

Output:

- `results/d_action_value.csv`

## Question

Claude critique B asks whether the controller is truly multi-point
curve-aware control, or only a binary `d=0` versus `d=3` switch.

The replay compares commit-aware dynamic-programming oracle value over:

- two-action set: `{d=0,d=3}`
- multi-action set: `{d=0,d=1,d=3,d=7}`

## Result

| scope | two-action oracle ms/tok | multi-action oracle ms/tok | multi gain | multi oracle choices | d1/d7 chosen |
|---|---:|---:|---:|---|---|
| mixed | 8.090088 | 8.090088 | 0.000% | d0=1148;d3=408 | false |
| chat | 10.524435 | 10.524435 | 0.000% | d0=368;d3=56 | false |
| chat_low | 10.640775 | 10.640775 | 0.000% | d0=593;d3=60 | false |
| code | 5.029230 | 5.029230 | 0.000% | d0=49;d3=118 | false |
| rag | 5.630443 | 5.630443 | 0.000% | d0=69;d3=122 | false |
| structured | 6.659242 | 6.659242 | 0.000% | d0=69;d3=52 | false |

Fixed-policy diagnostics from `results/d_action_value.csv` show:

- `d=1` is never the best fixed action.
- `d=7` is much worse than `d=3` in every scope.
- The classified `d=7` failure reason is `T8_verify_cost_dominates`.

## Gate

The multi-point gate fails; the two-action honesty gate passes.

Interpretation:

The current data do not support a smooth multi-point controller story. The
honest framing is:

```text
curve-gated speculation over {d=0,d=3}
```

not:

```text
continuous verifier-curve optimization over many d values
```

This does not invalidate VeriCurve-RV. It narrows the controller contribution:
the shaped curve opens a useful `d=3` operating point, while the selected-only
controller is a simple two-action gate.
