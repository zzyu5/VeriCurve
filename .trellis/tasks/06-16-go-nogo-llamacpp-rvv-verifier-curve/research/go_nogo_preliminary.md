# Preliminary Go/No-Go

## Label

```text
GO-kernel-gap / CONDITIONAL-system
```

## Why Not NO-GO

The direction is not dead:

1. llama.cpp latest upstream has active RISC-V/RVV backend support and configures on `rvv`.
2. `ggml-cpu` and `ggml` RVV backend components compiled successfully under low-risk `-j1`.
3. The current speculative decoding path naturally forms target verification batches where `T = n_draft + 1`.
4. Current RISC-V low-bit source contains a tension that is exactly relevant to VeriCurve-RV:
   - many direct vec-dot kernels assert `nrc == 1`;
   - RISC-V repack traits can select `16x1` GEMV/GEMM paths under compatible VLEN/shape conditions.
5. A bounded RVV CPU `llama-bench` run on an existing Q4_0 model produced a
   usable `C_old(T)` curve for `T in {1,2,4,8,16}`.

This is enough to justify moving from source/build reconnaissance to a minimal
T-specialized verifier-kernel experiment.

## C_old(T) Evidence

Measured setup:

```text
host: ssh rvv
source tree: /home/ubuntu/llama_integ
build commit: 6eab471
backend: CPU/RVV, no BLAS
model: /home/ubuntu/llama-2-7b-chat.Q4_0.gguf
threads: 1
prompt tokens as T proxy: 1,2,4,8,16
runs per T: 3
raw result: /home/ubuntu/vericurve-rv-lab/results/C_old_prompt_T_llama_integ_cpu_rvv_threads1.json
```

Parsed summary:

```text
T=1   avg_ms= 5318.608  total_ratio= 1.000  per_token_ratio=1.000
T=2   avg_ms=10453.514  total_ratio= 1.965  per_token_ratio=0.983
T=4   avg_ms=20882.991  total_ratio= 3.926  per_token_ratio=0.982
T=8   avg_ms=41236.657  total_ratio= 7.753  per_token_ratio=0.969
T=16  avg_ms=82762.715  total_ratio=15.561  per_token_ratio=0.973
```

Behavioral classification for this setup:

```text
repeated_t1-like
```

The total curve is close to linear in T. The current path has only a small
per-token improvement, not a strong multi-RHS compression.

## Why Not GO-Strong Yet

The result is strong enough to continue, but not enough to claim final system
speedup.

Missing evidence:

1. We have not traced which exact low-bit internal path produced the measured
   curve.
2. We have not implemented or measured `C_new(4)` or `C_new(8)`.
3. We have not measured `C_draft(d)`.
4. We have not measured acceptance, accepted tokens, or end-to-end speculative
   throughput.

Therefore the full-system label remains conditional.

## Immediate Next Task

Create a minimal T4 verifier-kernel task with these first steps:

1. Add minimal tracing around the measured path to determine whether Q4_0 uses
   direct `ggml_vec_dot_q4_0_q8_0`, RISC-V repack `16x1`, or another CPU path.
2. Build the smallest standalone harness that reproduces the measured Q4_0 x
   Q8_0 inner loop on `rvv`.
3. Implement T4 first, not a broad family:

```text
T = 4
quant = Q4_0 x Q8_0
threads = 1
metric = C_new(4) / C_old(4) and C_new(4) / C_old(1)
```

4. Compare against the existing `C_old(T)` result before touching the
   speculative runtime/controller.
5. Keep all remote work bounded by the same `rvv` safety policy.

## Recommended Remote Policy

Continue to use:

```text
/home/ubuntu/vericurve-rv-lab/ for new artifacts/results
/home/ubuntu/llama_integ only when reusing the already-built RVV baseline
nice -n 10
timeout
-j1 by default
```

Do not switch to high parallelism. If a longer build is necessary, prefer a longer timeout over more cores. If the machine remains idle and faster progress is needed, ask before trying `-j2`.

## Decision

Proceed with VeriCurve-RV, but frame the next milestone as characterization, not performance success:

```text
Phase 0/1 GO: current-source, remote-build, and first C_old(T) evidence are positive.
Kernel GO: old RVV CPU Q4_0 prompt-pass behavior is repeated_t1-like enough to leave room for T4/T8 curve shaping.
System GO: still conditional on C_new(T), C_draft(d), acceptance, and workload drift.
```

More specific post-Experiment-1 labels:

```text
GO-kernel-gap
GO-minimal-T4-kernel
CONDITIONAL-controller
CONDITIONAL-full-system
```

The next task should not begin with a broad scheduler. It should first trace the
current T path, then run a ggml-level C_old(T) microbenchmark, then implement
or reject a minimal T4 verifier microkernel.
