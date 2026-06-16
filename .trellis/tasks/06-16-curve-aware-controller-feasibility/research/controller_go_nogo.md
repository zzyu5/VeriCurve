# Controller Go/No-Go

Artifacts:

```text
results/controller_go_nogo.csv
results/oracle_by_workload.csv
results/Jd_offline_summary.csv
scripts/offline_jd_controller.py
```

## Baselines

The controller table uses the four real buckets for mixed evaluation:

```text
chat
code
rag
structured
```

It does not average in the already-concatenated `mixed` bucket, to avoid
double-counting.

Baseline results:

```text
B0 no speculation:              12.024 ms/token
B2 fixed d=3:                    9.048 ms/token
B4 offline-best fixed mixed:     9.048 ms/token
B5 goodput-only adaptive:       31.193 ms/token
B6 VeriCurve-RV offline:         8.226 ms/token
B7 oracle:                       7.190 ms/token
```

Relative to VeriCurve-RV offline:

```text
B0 no speculation:             1.462x slower
B4 offline-best fixed mixed:   1.100x slower
B5 goodput-only adaptive:      3.792x slower
B7 oracle:                     0.874x of VeriCurve-RV cost
```

## Oracle Scoring

Oracle uses actual accepted prefix from `acceptance_raw.csv` and may choose
source/d per position. It is scored as:

```text
total verifier+draft cost / total emitted tokens
```

This is intentionally the same ratio family as `J(d)`. It is not the mean of
per-position `cost/tokens`, because that creates a different statistic and can
make oracle comparisons misleading.

Oracle by workload:

```text
chat:       11.183 ms/token
code:        5.163 ms/token
rag:         6.384 ms/token
structured:  6.030 ms/token
```

## Gate Check

Full-system gate from the PRD:

```text
1. beat offline-best fixed d over mixed workload by >= 8-10%
2. reach >= 90% oracle
3. no regression on low-acceptance workload
```

Observed:

```text
beat offline-best fixed:
  9.047758 / 8.225712 = 1.099936
  about 10.0% better
  pass

oracle reach:
  7.189835 / 8.225712 = 0.874068
  87.4% of oracle
  fail strict >=90% gate

low-acceptance chat:
  VeriCurve chooses d=0
  no regression versus no speculation
  pass
```

The goodput-only adaptive baseline is much worse because it chooses large `d`
from acceptance alone while ignoring verifier cost. This supports the need for
curve-aware cost modeling.

## Decision

```text
Status: CONDITIONAL PAPER GO, not FULL SYSTEM GO
```

This is stronger than the weakest conditional case because the proxy
VeriCurve-RV offline policy beats the best fixed mixed policy by about 10%.
However, it misses the strict oracle threshold and still uses proxy acceptance,
so it should not be promoted to full-system go.

It is also not a controller no-go:

```text
offline-best fixed d does not match within 3-5%
goodput-only adaptive is far worse
low-acceptance chat is protected by d=0
```

## Next Required Step

The next round should convert this offline feasibility into a more realistic
controller test:

```text
replace proxy acceptance with real llama.cpp traces or a controlled
self-speculative path

evaluate an online EWMA controller with a switching margin and update window

keep d candidates focused on {0,1,3,7}; d=15 is less reliable until T=16 is a
native verifier measurement
```
