# Claude Critique Resolution Final

Date: 2026-06-17 Asia/Shanghai

Primary script:

```text
scripts/resolve_claude_critique.py
```

Primary outputs:

```text
results/regime_shift_table.csv
results/d_action_value.csv
results/selected_only_policy_summary.csv
results/selected_only_policy_trace.csv
results/goodput_baseline_comparison.csv
results/curve_robustness_matrix.csv
results/final_decision_matrix.csv
```

## Final Decision Matrix

A. Curve-shaping beyond kernel speedup:

```text
status: GO
evidence:
  code/rag/structured shift from old-curve best d=0 to new-curve best d=3.
  chat/chat_low remain best at d=0.
interpretation:
  The shaped verifier curve changes speculation viability; this is more than
  reporting a faster row-blocked kernel.
```

B. Two-action vs multi-point controller:

```text
status: TWO-ACTION
evidence:
  multi_vs_two_oracle_gain_pct = 0.000
  multi-action oracle choices = d0=1148;d3=408
  d1/d7 are never chosen by oracle.
interpretation:
  Frame the controller as curve-gated speculation over {d=0,d=3}, not as
  continuous multi-point curve optimization.
```

C. Selected-only controller:

```text
status: CONDITIONAL
evidence:
  best selected-only curve-aware policy = vericurve_selected_t0.4_p16
  ms/token = 9.078115
  speedup vs fixed d3 = 12.888843%
  oracle reach = 0.891164
  low-acceptance regression vs d0 = 0.544128%
interpretation:
  It beats fixed d3 and protects low-acceptance workloads, but misses the
  strict >=90% oracle gate and has no measured runtime overhead yet.
```

D. Goodput-only comparison:

```text
status: TIE
evidence:
  curve-aware selected ms/token = 9.078115
  best goodput-only selected ms/token = 9.160689
  curve-aware advantage over goodput-only = 0.909594%
interpretation:
  The controller algorithm is not a strong novelty claim. A goodput-only
  selected baseline nearly matches it.
```

E. Robustness across model/quant/working-set:

```text
status: SCOPED
evidence:
  rows512 shaped T4/T1 = 1.399368
  rows128 shaped T4/T1 = 1.701057
  rows2048 shaped T4/T1 = 2.839325
  no cross-quant shaped case yet
  no real-layer-specific shaped case beyond the synthetic n=11008 harness yet
interpretation:
  The core curve-shaping result is real but scoped. Larger working set weakens
  the strict curve ratio.
```

Final paper version:

```text
B. Curve-shaping systems paper:
  RTile x TTile verifier reshapes C_verify(T), and the shaped curve changes
  which speculation policies are viable.
```

Recommended next action:

```text
Do not spend the next round trying to make the selected-only controller look
like a major algorithmic contribution. Instead:

1. Write the paper around verifier cost-curve shaping and regime shift.
2. Present the controller as a simple two-action curve-gated policy analysis.
3. Add one targeted robustness experiment if possible:
   - alternate quant shaped case, or
   - real layer/working-set case explaining why rows2048 degrades.
4. If pursuing Version A later, implement real runtime choose_d and measure
   overhead; otherwise keep selected-only replay as conditional support.
```
