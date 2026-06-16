# A4 Curve-Shaping Go/No-Go

Summary CSV:

```text
results/curve_shaping_summary.csv
```

## Required Evidence

```text
C_old_T1 = 12.024 ms
C_old_T4 = 48.085 ms
C_best_T1 = 12.024 ms
C_candidate_T4_no_pack = 20.856 ms
C_candidate_T4_with_pack = 16.826 ms
C_candidate_T4_total = 16.826 ms
speedup_vs_old_T4 = 2.858 x
C_candidate_T4_total / C_old_T4 = 0.350
curve_ratio = C_candidate_T4_total / C_best_T1 = 1.399
correctness_max_abs = 0
correctness_max_rel = 0
```

Best candidate:

```text
R8 Layout2_rowblocked_weights
```

## Decision

```text
STRONG GO
```

The pro2 STRONG GO criteria are:

```text
C_candidate_T4_total / C_best_T1 <= 2.5
and
C_candidate_T4_total <= 0.65 x C_old_T4
```

Observed:

```text
1.399 <= 2.5
0.350 <= 0.65
```

## Interpretation

This does not rescue the failed direct R1T4 design. It changes the research
answer:

```text
direct R1T4: NO-GO
layout-aware RTile x TTile: STRONG GO
```

The viable next VeriCurve-RV kernel is row-blocked RTile x TTile, with R8T4 as
the current best harness point on this VLEN=128 RVV machine.

Controller work is no longer blocked by the absence of `C_new(T)`, but it
should use the measured row-blocked curve rather than the failed direct kernel.
