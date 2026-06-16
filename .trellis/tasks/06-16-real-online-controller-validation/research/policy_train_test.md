# Policy Train/Test Replay

Artifacts:

```text
results/policy_train_test.csv
scripts/replay_policy_family.py
```

Split:

```text
For each workload/chunk, the first half of recorded positions is train and the
second half is test.
```

This split is only a guard against obvious parameter overfitting in scan mode.
It is not a substitute for independent prompts or a commit-aware selected-path
trace.

## Best Tuned Scan-Mode Policy

The best train-ranked row is:

```text
policy: selected_threshold_d3_vs_d0
parameters: threshold=0.5; alpha=0.3; explore_period=8; min_d3_samples=4

train:
  ms/token: 10.553
  relative to train fixed d=3: 0.871
  oracle reach: 82.8%
  choices: d0=595,d3=180

test:
  ms/token: 8.146
  relative to test fixed d=3: 0.916
  oracle reach: 85.5%
  choices: d0=467,d3=314
```

Several nearby threshold settings behave similarly. The test result still beats
fixed d=3 by more than 5% in scan mode, but oracle reach remains below the
strict 88-90% target.

## Interpretation

```text
train/test does not erase the controller opportunity
threshold tuning does not close the oracle gap
scan-mode improvement cannot be promoted to online evidence
```

The tuned policy family is useful for the next runtime experiment:

```text
arms = {0,3}
threshold around 0.4-0.6 accepted tokens for d=3
periodic d=3 probing every 8-16 recorded steps
```

## Decision

```text
train/test policy replay: CONDITIONAL
selected-only online claim: NOT PROVEN
```

The next experiment should generate a position-complete trace or patch a
runtime selected-only `choose_d()` loop. More scan-mode tuning is unlikely to
settle the Go/No-Go.
