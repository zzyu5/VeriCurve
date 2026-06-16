# Oracle Gap Breakdown

Artifacts:

```text
results/oracle_gap_breakdown.csv
results/aligned_replay_summary.csv
scripts/replay_policy_family.py
```

Scope:

```text
recorded_position_scan
```

This is a diagnostic decomposition of the previous full-info replay. It is not
a selected-path online result.

## Mixed Result

```text
fixed d=3:                 10.248 ms/token
full-info EWMA:             9.035 ms/token
scan oracle:                7.666 ms/token
full-info EWMA oracle reach: 84.9%
```

The full-info EWMA still leaves a large scan-oracle gap:

```text
excess cost at oracle rate: 3228.881 ms
```

## Per-Workload Reach

```text
chat:
  EWMA 12.968 vs oracle 10.524, reach 81.2%
  EWMA choices d0=338,d3=86
  oracle choices d0=368,d3=56

chat_low:
  EWMA 12.433 vs oracle 10.608, reach 85.3%
  EWMA choices d0=543,d3=110
  oracle choices d0=593,d3=58,d7=2

code:
  EWMA 5.144 vs oracle 5.029, reach 97.8%
  EWMA choices d0=40,d3=127
  oracle choices d0=49,d3=118

rag:
  EWMA 5.994 vs oracle 5.630, reach 93.9%
  EWMA choices d0=44,d3=147
  oracle choices d0=69,d3=122

structured:
  EWMA 7.203 vs oracle 6.536, reach 90.7%
  EWMA choices d0=49,d3=72
  oracle choices d0=69,d3=30,d7=22
```

The gap is dominated by low-acceptance chat/chat_low and by workload/phase
transitions where the EWMA either keeps d=3 too long or falls back to d=0 while
oracle would use d=3.

## Regret Hotspots

Largest mixed scan-mode mismatch buckets:

```text
choosing d3 when oracle chooses d0:
  247 steps
  excess cost at oracle rate: 1186.377 ms

staying d0 when oracle chooses d3:
  109 steps
  excess cost at oracle rate: 886.736 ms

staying d0 when oracle chooses d7:
  4 steps
  excess cost at oracle rate: 96.576 ms
```

By policy action:

```text
EWMA chose d3:
  542 steps
  excess cost at oracle rate: 2245.568 ms

EWMA chose d0:
  1014 steps
  excess cost at oracle rate: 983.312 ms
```

Interpretation:

```text
1. d=1 is not useful in the current data.
2. d=7 is useful only to the scan oracle in some high-acceptance positions, but
   it is too risky for simple goodput-only control.
3. A two-action controller over d in {0,3} is a reasonable next policy family.
4. The full-info EWMA gap is not only an exploration problem; the switching
   rule and adaptation lag also matter.
```

## Decision

```text
Controller opportunity: still present
Full-info EWMA: still below 90% oracle
Selected-only controller: not proven by this decomposition
```
