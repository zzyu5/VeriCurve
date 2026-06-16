# Selected-Only Policy Replay

Date: 2026-06-17 Asia/Shanghai

Inputs:

- `results/position_complete_candidate_trace.csv`
- `../06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv`
- `scripts/resolve_claude_critique.py`

Outputs:

- `results/selected_only_policy_summary.csv`
- `results/selected_only_policy_trace.csv`

## Question

Claude critique C asks whether the replay leaks full candidate information.
This run evaluates selected-only policies: the policy observes only the outcome
of the selected arm and any explicit probe decisions.

Primary VeriCurve policy:

```text
actions = {d=0,d=3}
threshold = 0.4
alpha = 0.3
probe_interval = 16
min_samples = 4
switch_margin = 5%
fallback = d=0
```

## Mixed Result

| policy | ms/tok | speedup vs fixed d3 | oracle reach | low-accept regression vs d0 | probe-like decisions | choices |
|---|---:|---:|---:|---:|---:|---|
| fixed_d0 | 12.024267 | -17.3308% | 0.672813 | 0.000000% | n/a | d0=2550 |
| fixed_d3 | 10.248179 | 0.0000% | 0.789417 | 18.214478% | n/a | d3=1556 |
| oracle_multipoint | 8.090088 | 26.6757% | 1.000000 | -11.892886% | n/a | d0=1148;d3=408 |
| vericurve_selected_t0.4_p16 | 9.078115 | 12.8888% | 0.891164 | 0.544128% | 8.266361% | d0=1274;d3=468 |
| vericurve_selected_t0.5_p16 | 9.113908 | 12.4527% | 0.887664 | 0.418820% | 8.266819% | d0=1297;d3=457 |

Controller overhead:

```text
not measured in runtime; replay-only scalar overhead is not counted
```

## Gate

Status: CONDITIONAL.

Passes:

- Beats fixed `d=3` by more than 8%: `12.8888%`.
- Low-acceptance regression is below 3%: `0.544128%`.
- Uses selected-only observations, not full candidate information.

Fails or remains unproven:

- Oracle reach is `0.891164`, below the strict `>=0.90` full-system gate.
- Runtime controller overhead is not measured.
- Goodput-only selected baseline is within 1%, so controller algorithm novelty
  is weak.

Interpretation:

This is good enough for a curve-shaping systems paper, but not enough for a
strong full-system controller claim. The selected-only replay should be
described as conditional evidence unless a runtime `choose_d()` loop improves
oracle reach and measures overhead.
