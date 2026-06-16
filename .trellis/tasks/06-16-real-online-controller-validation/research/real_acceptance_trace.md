# Real Acceptance Trace

Artifacts:

```text
results/real_acceptance_trace.csv
results/controlled_lookup_Jd_estimate.csv
results/online_controller_trace.csv
results/online_controller_trace_summary.csv
artifacts/lookup_stats_*
artifacts/lookup_step_trace_*
patches/llamacpp_acceptance_trace.patch
```

## What Was Measured

This round moved from the prior pure Python proxy to llama.cpp's own
`examples/lookup` path.

Two levels of evidence were collected:

```text
1. aggregate controlled lookup-stats for d in {1,3,7}
2. patched per-step lookup-stats trace for d=3
```

The controlled path uses:

```text
binary: /home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve/bin/llama-lookup-stats
model: /home/ubuntu/llama-2-7b-chat.Q4_0.gguf
threads: 1
ctx requested: 64
actual n_ctx_seq after fit: 256
draft source: llama.cpp prompt lookup / ngram cache
```

It loads the real llama.cpp model/tokenizer/context, but it does not run target
decode for every token. It treats prompt text as predetermined output and
simulates lookup acceptance. Therefore this is stronger than the Python proxy
but still not final end-to-end speculative decoding evidence.

## Aggregate Results

Estimated `E_accept` from aggregate lookup-stats:

```text
chat_low:
  d=1 E=0.800
  d=3 E=1.663
  d=7 E=2.301

chat:
  d=1 E=0.813
  d=3 E=1.509
  d=7 E=2.234

code:
  d=1 E=0.983
  d=3 E=2.883
  d=7 E=6.395

rag:
  d=1 E=0.923
  d=3 E=2.476
  d=7 E=4.472

structured:
  d=1 E=0.844
  d=3 E=2.045
  d=7 E=3.226
```

Using the inherited `C_verify_best(T)` curve, the aggregate estimate selects
`d=3` for every measured workload.

## Per-Step Trace

The patch adds:

```text
VERICURVE_LOOKUP_TRACE_CSV=/path/to/out.csv
```

When set, `llama-lookup-stats` emits:

```text
chunk_id
step_id
requested_d
drafted_count
accepted_count
pseudo_size_before
pseudo_size_after
trace_draft_update_us
```

Per-step d=3 summary:

```text
chat:       424 steps, 64 draft steps, 171 drafted, 86 accepted
chat_low:   653 steps, 73 draft steps, 202 drafted, 112 accepted
code:       167 steps, 121 draft steps, 359 drafted, 345 accepted
rag:        191 steps, 130 draft steps, 389 drafted, 321 accepted
structured: 121 steps, 66 draft steps, 198 drafted, 135 accepted
```

This proves the trace plumbing works and records acceptance drift within a
llama.cpp path.

## Interpretation

The controlled lookup path shows high acceptance on repeated/template-heavy
inputs. This supports the claim that the shaped R8T4 verifier curve can turn
prompt-lookup speculation into a profitable region.

However, it does not yet support a strong controller claim. Under this
controlled aggregate estimate, `d=3` is best for every measured workload. That
means a fixed `d=3` baseline remains strong.

The important negative finding is:

```text
template tokens such as User/Assistant and repeated record structure can inflate
lookup acceptance even in nominal chat workloads.
```

Future real traces must include lower-template, model-generated chat or random
QA outputs if the controller claim depends on low-acceptance fallback behavior.

## Decision

```text
Trace plumbing: GO
Controlled lookup acceptance: GO
Controller-value evidence from this trace: WEAK / CONDITIONAL
```

This result keeps the project alive but does not promote it to full-system go.
