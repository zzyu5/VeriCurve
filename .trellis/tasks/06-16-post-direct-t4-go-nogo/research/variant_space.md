# B1 Variant Space

This task used the RTile matrix as the minimal schedule-variant space:

```text
old_vecdot_nrc1
R1_no_pack
R2_no_pack
R4_no_pack
R8_no_pack
```

The variants are not a broad scheduler implementation. They are enough to test
whether different T buckets prefer different verifier schedules.

Artifacts:

```text
results/variant_manifest.csv
results/variant_timing.csv
results/variant_decision_summary.csv
```

Timing buckets:

```text
T in {1,2,4,8}
```

`T=16` was not included in the variant matrix to keep the remote run short and
because A4 already reached STRONG GO. The old-path cache sweep still measured
T=16 for characterization.
