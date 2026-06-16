# C Cache-Aware Characterization

Artifacts:

```text
results/cache_characterization.csv
results/synthetic_workingset_sweep.csv
```

This branch used a synthetic working-set sweep on the old current path:

```text
bench_qmatmul_T 11008 <rows> 3
rows in {32,128,512,2048}
T in {1,2,4,8,16}
path = ggml_vec_dot_q4_0_q8_0_nrc1
```

No perf counters were used in this task, to avoid extra system permissions or
long remote runs.

## Observed Slopes

For rows 32, 128, and 512, the old path is close to linear:

```text
rows=32:  T16/T1 = 16.053
rows=128: T16/T1 = 15.999
rows=512: T16/T1 = 15.994
```

For rows 2048, the high-T slope changes:

```text
rows=2048:
  T2/T1  = 2.072
  T4/T1  = 4.005
  T8/T1  = 8.004
  T16/T1 = 10.157
```

This indicates a synthetic working-set effect at the largest row count,
especially at T=16.

## Decision

```text
CONDITIONAL
```

Rationale:

```text
There is a visible synthetic working-set slope change, but this task did not
collect perf counters, multiple quantizations, or real model-size sweeps.
```

Cache characterization remains a possible supporting explanation, not the best
primary paper direction after A reached STRONG GO.
