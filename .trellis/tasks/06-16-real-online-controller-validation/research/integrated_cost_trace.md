# Integrated Cost Trace

Artifacts:

```text
results/integrated_cost_trace.csv
artifacts/smoke_lookup_d3_b64.stderr
artifacts/smoke_lookup_d3_b64.stdout
artifacts/smoke_lookup_d3.stderr
```

## Successful Smoke

Command class:

```text
GGML_VERICURVE_TRACE=1
llama-lookup
model: /home/ubuntu/llama-2-7b-chat.Q4_0.gguf
threads: 1
d: 3
n_predict: 8
ctx: 256
batch/ubatch: 64
```

Result:

```text
status: success
encoded: 16 tokens in 84.914 s
decoded: 9 tokens in 43.387 s
n_draft: 3
n_drafted: 0
n_accept: 0
GGML_VERICURVE_TRACE q4_0_q8_0 call_count: 34,964,992
last_n: 11008
last_nrc: 1
```

This proves the real llama.cpp lookup decode path can run on `rvv` with the
current RVV build and low-bit trace instrumentation.

## Failed Smoke

The first smoke run used:

```text
batch/ubatch: 8
```

It failed with:

```text
GGML_ASSERT(n_tokens_all <= cparams.n_batch) failed
```

Reason:

```text
The prompt token count exceeded the requested batch size.
```

The fix was to use `-b 64 -ub 64`.

## Interpretation

The integrated path is runnable but too slow for broad sweeps with this 7B Q4
model:

```text
prompt eval: about 0.19 tokens/s
decode: about 0.18 tokens/s
```

This makes full real-decode sweeps expensive on the shared `rvv` host. The
current smoke prompt also produced zero drafted lookup tokens, so it does not
provide useful acceptance data.

## Decision

```text
Integrated decode smoke: CONDITIONAL
```

Next integrated-path work should either:

```text
use a smaller real model,
use prompts known to trigger prompt lookup,
or run fewer but longer targeted traces during an idle window.
```

Do not claim full end-to-end controller speedup from this smoke.
