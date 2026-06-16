# Workload Hardening

Artifact:

```text
results/aligned_replay_by_workload.csv
```

## Motivation

`pro5.md` noted that `chat_low` was not low enough in the aggregate lookup
sweep. This was partly true: aggregate sweeps over separate trajectories made
`d=3` appear best even for chat-like workloads.

Aligned replay gives a clearer picture:

```text
chat fixed d=0:     12.024 ms/token
chat fixed d=3:     13.990 ms/token

chat_low fixed d=0: 12.024 ms/token
chat_low fixed d=3: 14.364 ms/token
```

Therefore the current aligned replay already contains low-acceptance workloads
where speculation should be disabled.

## High-Acceptance Workloads

```text
code fixed d=3:       5.489 ms/token
rag fixed d=3:        6.278 ms/token
structured fixed d=3: 7.954 ms/token
```

These remain high-acceptance workloads where the shaped T=4 verifier curve is
useful.

## Decision

```text
Workload drift: GO for aligned replay
```

The controller now has a real workload-dependent decision:

```text
chat/chat_low -> d=0
code/rag/structured -> d=3
```

Future end-to-end runs should still add lower-template real generated chat and
possibly temperature > 0 traces, but the immediate blocker has shifted from
workload hardening to selected-only online control.
