# Curve Profiler Contract

The profiler measures the cost surfaces that feed the controller and paper analysis.

## Required Curves

```text
C_verify(T), T in {1,2,4,8,16}
C_draft(d), d in {1,3,7,15}
acceptance(d) by workload and draft source
```

## Minimum Profile Fields

```json
{
  "model": "model.gguf",
  "backend": "llama.cpp-rvv",
  "backend_commit": "commit",
  "quant": "Q4_K_M",
  "hardware": {
    "arch": "riscv64",
    "rvv": true,
    "vlen_bits": null,
    "threads": 1
  },
  "verify_curve": {
    "T1": {"latency_ms": 0.0, "per_position_ms": 0.0}
  },
  "draft_curve": {},
  "notes": []
}
```

## Measurement Rules

- Warmup and measurement iterations must be recorded.
- Use stable thread counts; do not mix results from different `--threads`.
- If hardware counters are unavailable, say so explicitly.
- Keep raw stdout/stderr next to parsed CSV/JSON.
- Never overwrite result files without preserving the old run or explaining why it was invalid.

## ggml-Level C_old(T) Microbenchmark

Model-level prompt-pass timing is an acceptable first signal, but it is not
enough to prove a low-bit verifier-kernel gap. Before writing the minimal T4
kernel, create or reuse a ggml-level benchmark that measures:

```text
quant = Q4_0 x Q8_0 first, unless trace selects a different low-bit path
T = 1,2,4,8,16
threads = 1
same model-like hidden size and row count across T
warmup + repeated measurement
trace path enabled or recorded
```

Required result columns:

```text
T
latency_ns or latency_ms
ratio_vs_T1
per_token_latency
trace_classification
repeat_count
```

Go/No-Go for the kernel gap:

```text
GO-T4-kernel:
  C_old_qmatmul(4) >= 3.4 * C_old_qmatmul(1)

CONDITIONAL:
  2.4 * C_old(1) <= C_old(4) < 3.4 * C_old(1)

NO-GO for low-bit T4 gap:
  C_old(4) < 2.2 * C_old(1)
```

## Profile Cache Key

The profile cache key should include:

```text
model architecture
model size
quantization format
backend commit
hardware id
RVV capability / VLEN if known
thread count
verifier kernel set
```
