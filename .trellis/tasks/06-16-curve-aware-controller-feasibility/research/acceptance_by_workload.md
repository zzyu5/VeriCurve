# acceptance(d) by Workload

Artifacts:

```text
results/acceptance_by_workload.csv
results/acceptance_raw.csv
scripts/cheap_draft_acceptance.py
```

## Purpose

Estimate whether different workload types create different profitable draft
budgets once the verifier curve has been reshaped.

The key controller question is not whether every workload benefits from
speculation. The key question is whether low-acceptance workloads and
high-acceptance workloads should choose different `d`.

## Method

Workload buckets:

```text
chat
code
rag
structured
mixed
```

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

Metric definitions:

```text
E_accept: mean accepted prefix length per draft round
acceptance_per_draft: E_accept / d
full_accept_rate: probability that all d draft tokens are accepted
```

The result is a deterministic ngram proxy over fixed tokenized workloads. It is
not a real llama.cpp sampling acceptance measurement.

## Key Results

Low-acceptance chat:

```text
chat ngram-map/mod:
  d=1  E_accept = 0.079
  d=3  E_accept = 0.101
  d=7  E_accept = 0.105
  d=15 E_accept = 0.115
```

High-repetition code:

```text
code ngram-map:
  d=1  E_accept = 0.746
  d=3  E_accept = 2.101
  d=7  E_accept = 4.323
  d=15 E_accept = 6.333
```

RAG-like repeated context:

```text
rag ngram-map:
  d=1  E_accept = 0.453
  d=3  E_accept = 1.083
  d=7  E_accept = 2.050
  d=15 E_accept = 2.903
```

Structured output:

```text
structured ngram-map:
  d=1  E_accept = 0.574
  d=3  E_accept = 1.293
  d=7  E_accept = 2.364
  d=15 E_accept = 3.750
```

Mixed workload:

```text
mixed ngram-map/mod:
  d=1  E_accept = 0.393
  d=3  E_accept = 0.971
  d=7  E_accept = 1.836
  d=15 E_accept = 2.734
```

## Interpretation

The workload buckets behave differently:

```text
chat: acceptance too low; speculation should usually stay off.
code: d=3 is strongly useful in the current verifier curve.
rag: d=3 is useful; larger d may overpay verifier cost.
structured: d=3 is useful; larger d improves acceptance but not necessarily J.
```

This is the behavior a curve-aware controller needs. It creates a real budget
choice instead of a single fixed `d` being obviously correct everywhere.

## Decision

```text
Status: GO for offline acceptance diversity
```

The acceptance proxy satisfies the controller-entry condition:

```text
at least two workloads have different optimal d
at least one workload chooses d=3
at least one low-acceptance workload chooses d=0
```

## Caveat

This is not sufficient for a final system claim. The next controller round
should replace this proxy with actual llama.cpp prompt/output traces or a
controlled self-speculative path.
