# Regime-Shift Analysis

Date: 2026-06-17 Asia/Shanghai

Inputs:

- `results/position_complete_candidate_trace.csv`
- `../06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv`
- `scripts/resolve_claude_critique.py`

Output:

- `results/regime_shift_table.csv`

## Question

Claude critique A asks whether the result is merely "R8T4 is a faster row-blocked
GEMM kernel." The necessary systems evidence is that the reshaped verifier
curve changes the speculation policy decision, not only the kernel latency.

The replay therefore compares fixed-d policies under:

- old verifier curve: `C_verify_old_ms`
- shaped/best verifier curve: `C_verify_best_ms`

Both use the same position-complete, commit-aware trace.

## Result

| workload | old best d | new best d | old best ms/tok | new best ms/tok | fixed d3 old | fixed d3 new | interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| chat | 0 | 0 | 12.024259 | 12.024259 | 39.978049 | 13.990175 | low acceptance stays no-spec |
| chat_low | 0 | 0 | 12.024281 | 12.024281 | 41.046454 | 14.363935 | low acceptance stays no-spec |
| code | 0 | 3 | 12.024259 | 5.488916 | 15.684723 | 5.488916 | regime shift to speculation |
| rag | 0 | 3 | 12.024267 | 6.277709 | 17.938781 | 6.277709 | regime shift to speculation |
| structured | 0 | 3 | 12.024255 | 7.953855 | 22.728617 | 7.953855 | regime shift to speculation |

## Gate

The gate passes.

Evidence:

- High-acceptance workloads (`code`, `rag`, `structured`) shift from best
  fixed `d=0` under the old curve to best fixed `d=3` under the shaped curve.
- Low-acceptance workloads (`chat`, `chat_low`) remain best at `d=0`.

Interpretation:

This is the strongest response to "just a fast kernel." The row-blocked
RTile x TTile kernel matters because it changes the verifier cost curve enough
to move the speculation break-even point. The correct contribution is therefore
not generic kernel novelty, but verifier-curve shaping plus policy implication.
