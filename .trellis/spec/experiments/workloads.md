# Workloads and Acceptance Drift

The controller must be evaluated where acceptance changes.

## Default Workload Buckets

- `chat`: low or unstable acceptance.
- `code`: potentially high ngram acceptance.
- `rag`: repeated context and templates.
- `structured`: JSON/tool/schema-like output with format repetition.
- `reasoning`: long outputs with phase-dependent drift.
- `mixed`: sequence of multiple workload types to force drift.

## Draft Sources

Start with:

```text
ngram
```

Add only if feasible:

```text
small draft model
MTP / self-speculative path
```

## Required Metrics

- `C_draft(d)`
- accepted tokens per round
- acceptance per draft token
- full accept probability
- tokens/s or ms/token
- oracle gap
- regression rate vs no speculation

## Prompt-Lookup Caveat

Prompt-lookup / ngram acceptance is highly sensitive to repeated template
tokens. A nominal `chat` workload with repeated `User:` / `Assistant:` framing
can behave like a structured workload and inflate acceptance.

When the controller claim needs a low-acceptance workload, include at least one
trace with low template repetition or real model-generated chat/random QA
output. Label repeated-template chat separately from low-acceptance chat.
