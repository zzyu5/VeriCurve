# Commit-Aware Train/Test

Artifacts:

```text
results/commit_aware_train_test.csv
scripts/replay_commit_aware.py
```

## Split

For each workload/chunk:

```text
train: positions before the chunk midpoint
test:  positions at or after the chunk midpoint
```

This keeps the replay position-complete inside each split.

## Best Train-Ranked Policy

```text
policy: selected_threshold_t0.4_p16
threshold: 0.4
alpha: 0.2
probe interval: 16
minimum d3 samples: 4
```

Train:

```text
ms/token: 9.873
relative to fixed d=3: 0.878
oracle reach: 88.0%
missing transitions: 0
```

Test:

```text
ms/token: 8.492
relative to fixed d=3: 0.920
oracle reach: 87.9%
missing transitions: 0
```

## Interpretation

The tuned two-action threshold policy still beats fixed d=3 on test by about
8.0%, but oracle reach stays below 90%.

## Decision

```text
train/test: CONDITIONAL
```

The policy is not just a scan-mode artifact, but it still misses the strict
full-system oracle threshold.
