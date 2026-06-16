# B2 Schedule Variant Go/No-Go

Decision summary:

```text
results/variant_decision_summary.csv
```

## Best Variant by T

```text
T=1: old_vecdot_nrc1
T=2: old_vecdot_nrc1
T=4: R8_no_pack
T=8: R8_no_pack
```

Best static variant over equal-weight `T in {1,2,4,8}`:

```text
R8_no_pack
latency_sum = 118.270 ms
```

Best dynamic selection:

```text
old_vecdot_nrc1 for T=1,2
R8_no_pack for T=4,8
latency_sum = 107.749 ms
dynamic_gain = 8.896%
```

Crossover:

```text
yes
```

Margins:

```text
T=1 best margin = 62.440%
T=2 best margin = 3.801%
T=4 best margin = 4.955%
T=8 best margin = 15.233%
```

## Decision

```text
GO-runtime-variant
```

The pro2 GO criteria require:

```text
at least two variants are best for different T buckets
margin >= 7% in at least two buckets
best-dynamic beats best-static by >= 8%
```

Observed:

```text
two best variants: old_vecdot_nrc1 and R8_no_pack
>=7% margin buckets: T=1 and T=8
dynamic gain: 8.896%
```

## Interpretation

Schedule-at-inference-time is a valid secondary direction. It should not replace
the A branch, because A already produced a stronger row-blocked R8T4 kernel
result. But the crossover is real enough that a future controller should choose
between old single-RHS and row-blocked verifier kernels based on T.
