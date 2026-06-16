# Two-Action Policy Replay

Artifacts:

```text
results/commit_aware_replay_summary.csv
results/commit_aware_replay_by_workload.csv
results/commit_aware_selected_threshold_trace.csv
```

## Policy Family

The pro7 policy family intentionally restricts actions to:

```text
d in {0,3}
```

Reason:

```text
d=1 has not shown useful advantage
d=7 is dangerous under goodput-only control
main workload split is low-acceptance d=0 vs high-acceptance d=3
```

The best selected-only policy in this sweep is:

```text
selected_threshold_t0.4_p16
```

It observes only selected d=3 outcomes and uses periodic d=3 probes:

```text
threshold = 0.4 accepted tokens
EWMA alpha = 0.3
probe interval = 16 steps
minimum d3 samples = 4
```

## Per-Workload Behavior

```text
chat:
  fixed d=0: 12.024
  fixed d=3: 13.990
  selected threshold: 12.217
  oracle reach: 86.1%

chat_low:
  fixed d=0: 12.024
  fixed d=3: 14.364
  selected threshold: 12.017
  oracle reach: 88.5%

code:
  fixed d=3: 5.489
  selected threshold: 5.269
  oracle reach: 95.5%

rag:
  fixed d=3: 6.278
  selected threshold: 6.213
  oracle reach: 90.6%

structured:
  fixed d=3: 7.954
  selected threshold: 7.429
  oracle reach: 89.6%
```

The policy chooses d=0 for low-acceptance chat/chat_low most of the time, while
still probing d=3. It chooses enough d=3 on code/rag/structured to improve over
fixed d=3 on code and structured, and stays close on rag.

## Go/No-Go

```text
beats fixed d=3 by >= 8%: yes
reaches >= 90% oracle: no, reaches 89.1%
low-acceptance regression > 3%: no
missing transitions: 0
```

Decision:

```text
two-action selected-only policy: CONDITIONAL / NEAR-GO
```

Do not add unrestricted d=7 yet. The next useful step is either a small runtime
`choose_d()` run for this two-action policy or a narrow tuning pass aimed at the
remaining oracle gap.
