# Prefix-State Equivalence

Artifacts:

```text
patches/pseudo_state_hash.patch
scripts/make_pseudo_state_hash_patch.py
results/prefix_state_equivalence.csv
artifacts/state_eq_*.csv
```

## Question

Can a teacher-forced d=0 prefix trace stand in for states reached by a d=3
committed trajectory?

Required property:

```text
same emitted target prefix -> same lookup pseudo state
```

## Method

`VERICURVE_LOOKUP_STATE_EQ_CSV` adds a disabled-by-default trace hook to
`examples/lookup/lookup-stats.cpp`.

For each d=3 committed position, it compares:

```text
d0_stepwise pseudo_output hash
d3_committed pseudo_output hash
d0_stepwise ngram context hash
d3_committed ngram context hash
candidate draft/accept signatures for d in {0,1,3,7}
```

The d0 path advances one target token at a time and updates the lookup context
cache with `common_ngram_cache_update(..., nnew=1)`. The d3 path is the actual
committed lookup-stats path.

## Results

All measured workloads pass:

```text
chat:       424 rows, pseudo/context/candidate mismatches = 0
chat_low:   653 rows, pseudo/context/candidate mismatches = 0
code:       167 rows, pseudo/context/candidate mismatches = 0
rag:        191 rows, pseudo/context/candidate mismatches = 0
structured: 121 rows, pseudo/context/candidate mismatches = 0
```

Candidate signatures also match for every checked d:

```text
d=0 mismatch: 0
d=1 mismatch: 0
d=3 mismatch: 0
d=7 mismatch: 0
```

## Interpretation

For this lookup-stats path:

```text
same emitted prefix is enough to reconstruct the same pseudo_output and
context ngram-cache state.
```

This is expected because `common_ngram_cache_draft` does not mutate the caches,
and both accepted and sampled tokens update the context cache one appended token
at a time.

## Decision

```text
prefix-state equivalence: GO
```

It is valid to build a position-complete teacher-forced candidate trace for the
current lookup-stats controller replay.
