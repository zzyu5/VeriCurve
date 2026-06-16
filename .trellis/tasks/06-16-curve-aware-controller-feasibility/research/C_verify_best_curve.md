# C_verify_best(T) Curve

Artifact:

```text
results/C_verify_best_curve.csv
```

## Purpose

This measurement answers whether the row-blocked `RTile x TTile` verifier path
creates a shaped verifier cost curve that a speculation controller can exploit.

It is not a new proof of the direct `R1T4` path. The direct path already failed
in the previous task. This round uses the row-blocked path as the candidate
verifier curve.

## Method

Candidate `T` values:

```text
T in {1,2,4,8,16}
d = T - 1
```

The table compares:

```text
old vecdot nrc=1 path
row-blocked / layout-aware candidate path
best dynamic variant per T
```

Important measurement notes:

```text
T=1 and T=4 old absolute values come from the same RTile harness used by the
previous post-direct task.

T=2, T=8, and T=16 old values are scaled from the same T=1 absolute value using
fresh old qmatmul ratios, because the standalone old qmatmul benchmark had a
different absolute baseline.

T=16 candidate is a composed estimate from two measured R8T8 tiles, not a
native R8T16 kernel.
```

## Result

```text
T=1:  best = 12.024 ms, winner = old_vecdot_nrc1
T=2:  best = 24.037 ms, winner = old_vecdot_nrc1
T=4:  best = 16.826 ms, winner = R8_rowblocked_weights_total
T=8:  best = 41.537 ms, winner = R8_no_pack
T=16: best = 83.074 ms, winner = two_R8T8_no_pack_tiles_composed
```

Derived curve ratios:

```text
C_best(4) / C_best(1) = 1.399
C_best(8) / C_best(1) = 3.454
C_best(16) / C_best(1) = 6.909
```

## Decision

```text
Status: GO
```

Reason:

```text
C_best(4) / C_best(1) = 1.399 <= 1.8
and there is a real crossover:
  T=1/T=2: old vecdot wins
  T>=4: row-blocked RTile x TTile variants win
```

This is the curve-shaping signal needed by the controller study. It supports
the pro3 direction: the mainline should be `RTile x TTile` verifier curve
shaping plus curve-aware speculation, not a T-visible direct kernel.

## Caveats

The `T=16` point should be treated as provisional because it is composed from
two `R8T8` tiles. It is sufficient for controller feasibility modeling, but a
native or cleaner tiled implementation is needed before paper-grade reporting.

The old curve values mix absolute values and scaled ratios in a controlled way.
The method is recorded in `old_curve_method` and should not be hidden in future
plots.
