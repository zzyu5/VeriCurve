# A3 Layout Ablation

## Layouts

The harness measured four layout classes for `T=4`:

```text
Layout0_no_packing:
  original row-major q4 weights and token-major q8 RHS.

Layout1_packed_rhs:
  q8 RHS repacked by K block, then token.

Layout2_rowblocked_weights:
  q4 weights repacked by row group, then K block, then row.

Layout3_packed_rhs_rowblocked_weights:
  both RHS packing and row-blocked weights.
```

Packing costs are measured separately and included in `C_total`.

Canonical CSV:

```text
results/layout_ablation.csv
```

## Key Results

Baseline from the same repeats=5 run:

```text
C_old_T1 = 12.024 ms
C_old_T4 = 48.085 ms
```

Best no-pack candidate:

```text
R8 Layout0_no_packing:
  C_kernel = 20.856 ms
  C_total = 20.856 ms
  C_total / old_T4 = 0.434
  C_total / old_T1 = 1.734
```

Best packed/layout candidate:

```text
R8 Layout2_rowblocked_weights:
  C_pack_weight_once = 2.909 ms
  C_kernel = 13.916 ms
  C_total = 16.826 ms
  C_total / old_T4 = 0.350
  C_total / old_T1 = 1.399
```

RHS packing alone was not the main win:

```text
R8 Layout1_packed_rhs:
  C_total = 20.185 ms
```

Combining RHS packing with row-blocking did not beat row-blocking alone:

```text
R8 Layout3_packed_rhs_rowblocked_weights:
  C_total = 16.848 ms
```

Correctness:

```text
max_abs = 0
max_rel = 0
```

## Interpretation

The useful layout is row-blocked q4 weights. RHS packing is cheap but does not
materially improve the best R8T4 path in this harness.

The row-blocked result is important because it includes one-time pack cost in
`C_total`. In a real model path, weight repacking should be amortized across
many verifier calls, so the kernel-only number is also relevant:

```text
R8 Layout2 kernel only = 13.916 ms
R8 Layout2 total with pack = 16.826 ms
```

For Go/No-Go, the conservative total with pack is used.
