# Replay Correctness Audit

Artifacts:

```text
scripts/replay_policy_family.py
results/replay_sanity_checks.csv
results/policy_family_replay.csv
```

## Audit Questions

### 1. Does the previous replay advance by selected accepted_count?

No.

`scripts/replay_aligned_controller.py` scans the recorded aligned rows in order.
It uses:

```text
emitted_tokens = 1 + accepted_count(d)
total cost / total emitted tokens
```

but it does not advance to:

```text
next pseudo_position = pseudo_position + emitted_tokens
```

This means the prior `aligned_replay_summary.csv` is a recorded-position scan,
not a commit-aware selected-path replay.

### 2. Is the previous oracle commit-aware?

No.

The previous oracle is a Dinkelbach fractional oracle over recorded positions.
It is correct for the scan-mode objective:

```text
choose one candidate row per recorded d=3-trajectory position
```

It is not a commit-aware path oracle because it does not skip positions after
selecting a candidate with accepted tokens.

### 3. Is fixed d=3 commit-aware on this trace?

Yes, for the committed trajectory.

The trace was collected while committing `d=3`, and the d=3 candidate next
positions are complete:

```text
mixed d=3:
  recorded positions: 1556
  present next-position: 1546
  missing next-position: 0
  terminal next-position: 10
```

This validates fixed d=3 and the committed-path reproduction check.

### 4. Are all policies currently replayable with the same commit/skip rule?

No.

The current aligned trace is not position-complete for non-d3 selected paths:

```text
mixed d=0:
  present next-position: 1144
  missing next-position: 402
  present fraction among nonterminal transitions: 0.740

mixed d=1:
  present next-position: 1228
  missing next-position: 318
  present fraction among nonterminal transitions: 0.794

mixed d=3:
  present next-position: 1546
  missing next-position: 0
  present fraction among nonterminal transitions: 1.000
```

The missing transitions are especially severe on high-acceptance workloads:

```text
code d=0 present fraction: 0.297
rag d=0 present fraction: 0.365
structured d=0 present fraction: 0.575
```

This is expected for a d=3 committed trajectory: when d=3 accepts tokens, it
skips intermediate pseudo positions that a d=0 policy would need.

### 5. Is total cost / total emitted tokens used?

Yes.

Both the previous replay and the new audit script aggregate as:

```text
sum(C_verify + C_draft) / sum(1 + accepted_count)
```

They do not average per-step ratios.

### 6. Is d=0 emitted token accounting correct?

Yes.

`d=0` has:

```text
accepted_count = 0
emitted_tokens = 1
```

The sanity check reports `emitted_tokens_min = 1` and `emitted_tokens_max = 1`
for all d=0 workloads.

### 7. Is d=7 failure a replay bug?

No for scan-mode fixed d=7.

The recorded-position scan has:

```text
fixed d=7: 19.100 ms/token
fixed d=3: 10.248 ms/token
```

The poor d=7 result comes from the high T=8 verifier cost relative to accepted
tokens, not from emitted-token accounting.

## Decision

```text
Replay correctness: CONDITIONAL / NOT SELECTED-ONLY PROVEN
```

What is valid:

```text
d=3 committed-path replay
recorded-position scan diagnostics
full-info upper-bound comparison on the recorded trajectory
```

What is not valid yet:

```text
claiming a real selected-only online controller
claiming scan-mode oracle as a commit-aware oracle
claiming policy numbers from early-stopped commit-aware replay when transitions
are missing
```

Required next evidence:

```text
position-complete aligned candidate trace, likely from a d=0 committed run, or
a real runtime choose_d loop that records only selected decisions and outcomes.
```
