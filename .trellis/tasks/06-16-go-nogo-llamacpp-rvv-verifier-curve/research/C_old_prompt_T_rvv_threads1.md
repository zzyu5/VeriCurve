# C_old(T) Prompt-Pass Measurement on `rvv`

## Decision Use

This is the first bounded measurement for Experiment 1. It uses llama.cpp
prompt evaluation time as the current-path `C_old(T)` proxy for target
verification width:

```text
T = prompt token count
threads = 1
quant = Q4_0
backend = CPU/RVV
```

It is not a full speculative-decoding controller experiment. It answers whether
the current RVV CPU path already amortizes T strongly enough to weaken the case
for a T-specialized verifier kernel.

## Safety Context

Remote preflight showed the shared `rvv` host was idle enough for a tiny,
single-thread benchmark:

```text
host: ubuntu
arch: riscv64
kernel: Linux 6.12.23
CPUs: 64
memory: 121 GiB
load before measurement: low
active TianchenRV / compiler / llama jobs: none observed
```

All build and benchmark commands used:

```text
nice -n 10
timeout
-j1 for build
threads = 1 for measurement
```

No sudo, package installation, system configuration, or TianchenRV working tree
operation was performed. The existing `control_repackON` and `canary_repackON`
trees were inspected only enough to identify them as instrumented and were not
used for the benchmark.

## Source Tree and Build

The measurement reused an existing RVV-only llama.cpp integration tree because
the fresh `~/vericurve-rv-lab/llama.cpp` checkout had not finished building
`llama-bench` within the cautious 600-second `-j1` window.

```text
remote source tree: /home/ubuntu/llama_integ
build dir: /home/ubuntu/llama_integ/build
llama.cpp commit: 6eab471
compiler shown by llama-cli: GNU 14.2.0 for Linux riscv64
GGML_CPU: ON
GGML_RVV: ON
GGML_NATIVE: ON
GGML_CPU_REPACK: ON
GGML_BLAS: OFF
```

This is a recent llama.cpp RVV build, not a measurement of the fresh upstream
clone's completed `llama-bench`. A same-session source comparison found the
relevant RISC-V Q4/Q8 files matched the fresh clone:

```text
ggml/src/ggml-cpu/arch/riscv/quants.c: same
ggml/src/ggml-cpu/repack.cpp: same
examples/speculative/speculative.cpp: same
common/sampling.cpp: same
```

Therefore this result is valid as current-path kernel-gap evidence, but it must
not be presented as a final latest-upstream performance claim.

The missing benchmark target was built with:

```bash
cd "$HOME/llama_integ"
nice -n 10 timeout 600 cmake --build build --target llama-bench -j1
```

Result:

```text
[100%] Built target llama-bench
```

Device listing:

```bash
./build/bin/llama-bench --list-devices
```

Result:

```text
Available devices:
  (none)
```

This is expected for the CPU backend. Benchmark rows reported:

```text
backends: CPU
cpu_info: CPU
```

The separate `/home/ubuntu/workspace/workspace3/llama.cpp` tree was not used
for evidence because its cache had `GGML_BLAS=ON` and `llama-bench` reported an
OpenBLAS backend.

## Model

Existing remote model:

```text
/home/ubuntu/llama-2-7b-chat.Q4_0.gguf
size: about 3.6 GiB
quant: Q4_0
```

No model was downloaded.

## Measurement Command

Remote command:

```bash
cd "$HOME/llama_integ"
mkdir -p "$HOME/vericurve-rv-lab/results"
nice -n 10 timeout 900 ./build/bin/llama-bench \
  -m "$HOME/llama-2-7b-chat.Q4_0.gguf" \
  -p 1,2,4,8,16 \
  -n 0 \
  -t 1 \
  -b 16 \
  -ub 16 \
  -r 3 \
  -o json \
  > "$HOME/vericurve-rv-lab/results/C_old_prompt_T_llama_integ_cpu_rvv_threads1.json"
```

Raw result path:

```text
/home/ubuntu/vericurve-rv-lab/results/C_old_prompt_T_llama_integ_cpu_rvv_threads1.json
```

## Parsed Results

```text
T,avg_ns,avg_ms,total_ratio,per_token_ms,per_token_ratio,avg_ts,stddev_ns,samples_ns
1,5318607974,5318.608,1.000,5318.608,1.000,0.188019,250142,[5318495661, 5318458041, 5318870222]
2,10453514406,10453.514,1.965,5226.757,0.983,0.191323,1060332,[10453458368, 10452488150, 10454596701]
4,20882991148,20882.991,3.926,5220.748,0.982,0.191576,335084888,[21269906956, 20687543505, 20691522985]
8,41236657243,41236.657,7.753,5154.582,0.969,0.194003,93643148,[41181786320, 41344782756, 41183402654]
16,82762714671,82762.715,15.561,5172.670,0.973,0.193326,310206326,[83012076649, 82415341253, 82860726111]
```

## Interpretation

The old path scales almost linearly in total prompt-pass cost:

```text
T=2  total cost: 1.965x T=1
T=4  total cost: 3.926x T=1
T=8  total cost: 7.753x T=1
T=16 total cost: 15.561x T=1
```

Per-token time improves only modestly:

```text
T=2  per-token cost: 0.983x T=1
T=4  per-token cost: 0.982x T=1
T=8  per-token cost: 0.969x T=1
T=16 per-token cost: 0.973x T=1
```

For this model, quantization, thread count, and backend configuration, current
llama.cpp/RVV CPU prompt evaluation does not show a strong T-direction cost
compression. It behaves close to repeated single-token work with a small
constant amortization.

## Current Path Classification

For the measured setup:

```text
current path label: repeated_t1-like
confidence: medium
```

The confidence is not high because this run did not include low-overhead call
tracing for `ggml_vec_dot_*`, `ggml_gemv_*_16x1_*`, or `ggml_gemm_*_16x1_*`.
Source evidence still shows direct RISC-V low-bit vec-dot kernels asserting
`nrc == 1`, while RISC-V repack traits exist for some shapes. The measurement
therefore establishes behavioral scaling, not the exact internal kernel path.

## Go/No-Go Consequence

This result is a positive signal for the next VeriCurve-RV stage:

```text
GO-kernel-gap
GO-minimal-T4-kernel
CONDITIONAL-controller
CONDITIONAL-full-system
```

Reason:

The existing RVV path leaves clear curve-shaping room. A T4 verifier kernel
does not need to beat an already-flat current path; it only needs to bend the
near-linear old curve enough to make `C_verify(T)` useful for controller
decisions.

It is not yet a full system GO. The missing evidence is:

```text
C_new(4) or C_new(8)
C_draft(d)
acceptance and accepted-token curves
workload drift
end-to-end speculative throughput
```
