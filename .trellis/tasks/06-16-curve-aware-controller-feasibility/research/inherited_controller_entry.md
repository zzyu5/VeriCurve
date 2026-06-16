# Inherited Controller Entry Evidence

Source task:

```text
.trellis/tasks/06-16-post-direct-t4-go-nogo
```

Key artifacts:

```text
research/final_go_nogo_summary.md
research/curve_shaping_go_nogo.md
results/curve_shaping_summary.csv
results/variant_decision_summary.csv
```

Controller entry facts:

```text
A. Curve-shaping kernel:
  status: STRONG GO
  C_old_T4 = 48.085 ms
  C_best_T1 = 12.024 ms
  C_candidate_T4_total = 16.826 ms
  speedup_vs_old_T4 = 2.858 x
  curve_ratio = 1.399

B. Schedule variant crossover:
  status: GO
  best_T1/T2 = old_vecdot_nrc1
  best_T4/T8 = R8_no_pack
  dynamic_gain = 8.896%

C. Cache-aware characterization:
  status: CONDITIONAL

D. Controller readiness:
  status: READY
```

Interpretation:

```text
The controller can now be evaluated, but it must use the row-blocked RTile x
TTile verifier curve. It must not use the failed direct R1T4 curve.
```
