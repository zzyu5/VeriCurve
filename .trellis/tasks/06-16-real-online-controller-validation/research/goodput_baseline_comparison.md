# Goodput-Only Baseline Comparison

Date: 2026-06-17 Asia/Shanghai

Inputs:

- `results/position_complete_candidate_trace.csv`
- `../06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv`
- `scripts/resolve_claude_critique.py`

Output:

- `results/goodput_baseline_comparison.csv`

## Question

Claude critique D asks whether a TurboSpec-style goodput-feedback policy over
the same shaped verifier can match the curve-aware controller.

This replay uses selected-only goodput policies. They do not choose from the
`C_verify(T)` table directly. They observe only:

```text
reward = emitted_tokens / observed_step_cost
```

The best goodput-only baseline in this run is:

```text
goodput_ucb_c0.02_p16
actions = {d=0,d=3}
probe_interval = 16
min_samples_per_arm = 4
```

## Result

| comparison | policy | ms/tok | speedup vs fixed d3 | oracle reach | choices |
|---|---|---:|---:|---:|---|
| best curve-aware selected | vericurve_selected_t0.4_p16 | 9.078115 | 12.888843% | 0.891164 | d0=1274;d3=468 |
| best goodput-only selected | goodput_ucb_c0.02_p16 | 9.160689 | 11.871269% | 0.883131 | d0=1246;d3=500 |
| fixed d3 | fixed_d3 | 10.248179 | 0.000000% | 0.789417 | d3=1556 |
| oracle | oracle_multipoint | 8.090088 | 26.675742% | 1.000000 | d0=1148;d3=408 |

Curve-aware advantage over the best goodput-only baseline:

```text
0.909594%
```

## Gate

Status: TIE.

The curve-aware selected policy does not beat goodput-only by the required
`>=5%`. The two are close enough that the controller algorithm should not be
sold as the main novelty.

Interpretation:

This strengthens the case for Version B:

```text
RTile x TTile verifier reshapes C_verify(T), and the shaped curve changes
which speculation policies are viable.
```

It weakens Version A:

```text
selected-only curve-aware controller as a strong new adaptive algorithm.
```
