# C_draft(d)

Artifacts:

```text
results/C_draft.csv
scripts/cheap_draft_acceptance.py
```

## Purpose

Measure whether cheap draft generation cost can erase the verifier-curve gain.
This round intentionally uses lightweight deterministic draft proxies before
attempting any larger draft model or invasive llama.cpp integration.

## Method

Draft sources:

```text
ngram-simple
ngram-map
ngram-mod
```

Draft budgets:

```text
d in {1,3,7,15}
```

The script was run on remote `rvv` under low priority:

```text
method: python_ngram_proxy_remote_cpu
repeats: 80
positions: 656
```

The proxy builds deterministic token histories over synthetic workload buckets.
It measures the CPU-side cost of generating one draft round. It does not measure
a real llama.cpp draft model.

## Result

Representative costs:

```text
ngram-simple:
  d=1  0.003973 ms
  d=3  0.005076 ms
  d=7  0.006756 ms
  d=15 0.009816 ms

ngram-map:
  d=1  0.019272 ms
  d=3  0.032868 ms
  d=7  0.059580 ms
  d=15 0.118287 ms

ngram-mod:
  d=1  0.012250 ms
  d=3  0.027651 ms
  d=7  0.051974 ms
  d=15 0.099627 ms
```

## Interpretation

Draft cost is far smaller than verifier cost in this proxy:

```text
C_verify_best(1)  = 12.024 ms
C_verify_best(4)  = 16.826 ms
C_verify_best(8)  = 41.537 ms
C_verify_best(16) = 83.074 ms
max C_draft       = 0.118 ms
```

Therefore the cheap-draft cost does not eat the R8T4 verifier-curve gain.

## Decision

```text
Status: GO for cheap-draft feasibility
```

This does not prove a full draft-model path. It proves that a low-overhead
controller and cheap deterministic draft source are plausible enough to continue
to acceptance and `J(d)` analysis.

## Caveat

Do not use this as a paper claim about draft model cost. It is a controller
feasibility proxy only.
