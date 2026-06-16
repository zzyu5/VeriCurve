# Current llama.cpp/RVV Path Trace: T1/T2/T4/T8

## Decision

```text
Task 1 label: GO-T4-kernel
```

Reason:

The traced fresh upstream clone uses the single-RHS RISC-V Q4_0 x Q8_0 vec-dot
path for T=1,2,4,8. The traced function is:

```text
ggml_vec_dot_q4_0_q8_0
```

The last observed `nrc` is always:

```text
nrc = 1
```

The call count scales approximately with T:

```text
T=1  call_ratio=1.000
T=2  call_ratio=1.981
T=4  call_ratio=3.942
T=8  call_ratio=7.866
```

This directly supports the previous behavioral conclusion that the old path is
repeated-T1-like and leaves room for a T4 verifier microkernel.

## Remote Safety Context

Remote preflight before this run:

```text
date: Tue Jun 16 02:46:14 UTC 2026
host: ubuntu
kernel: Linux 6.12.23 riscv64
CPUs: 64
memory: 121 GiB total, 119 GiB available
load average: 0.07, 0.20, 0.17
active TianchenRV / compiler / llama jobs: none observed
```

The build and trace used:

```text
nice -n 10
timeout
-j1 for build
threads = 1 for trace runs
```

No sudo, package installation, system configuration, or TianchenRV working tree
operation was performed.

Final residual-process check after trace:

```text
date: Tue Jun 16 03:25:08 UTC 2026
load average: 0.95, 1.11, 1.04
pgrep compile/llama patterns: no residual compile or llama process beyond the current pgrep shell
```

## Source Tree

Task-owned fresh clone:

```text
remote source tree: /home/ubuntu/vericurve-rv-lab/llama.cpp
commit: e36a602
subject: mtmd: fix miscounting n_tokens (#24656)
build dir: build-vericurve
```

The previous 600-second build window was too short for a fresh `llama-bench`
target. This run used a longer timeout while preserving `-j1`:

```bash
nice -n 10 timeout 3600 cmake --build build-vericurve --target llama-bench -j1
```

Result:

```text
[100%] Built target llama-bench
EXIT:0
```

Local build log:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/build_llama_bench_trace_e36a602.log
```

## Trace Patch

Patch artifact:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/patches/current_path_trace.patch
```

Patch application script:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/scripts/apply_current_path_trace.py
```

Trace mode:

```text
GGML_VERICURVE_TRACE=1
```

The patch aggregates counters and dumps one line at process exit. It does not
print inside inner loops.

Instrumented functions:

```text
ggml_vec_dot_q4_0_q8_0
ggml_gemv_q4_0_16x1_q8_0
ggml_gemm_q4_0_16x1_q8_0
```

Only `ggml_vec_dot_q4_0_q8_0` produced nonzero trace rows in this experiment.

## Trace Command

Remote command shape:

```bash
cd "$HOME/vericurve-rv-lab/llama.cpp"
for T in 1 2 4 8; do
  GGML_VERICURVE_TRACE=1 nice -n 10 timeout 600 \
    ./build-vericurve/bin/llama-bench \
      -m "$HOME/llama-2-7b-chat.Q4_0.gguf" \
      -p "$T" -n 0 -t 1 -b 16 -ub 16 -r 1 -o csv \
      > "$HOME/vericurve-rv-lab/minimal-t4/results/trace_llama_bench_T${T}.csv" \
      2> "$HOME/vericurve-rv-lab/minimal-t4/artifacts/trace_llama_bench_T${T}.stderr"
done
```

## Raw Artifacts

Local copies:

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/trace_llama_bench_T1.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/trace_llama_bench_T2.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/trace_llama_bench_T4.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/results/trace_llama_bench_T8.csv
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/trace_llama_bench_T1.stderr
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/trace_llama_bench_T2.stderr
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/trace_llama_bench_T4.stderr
.trellis/tasks/06-16-minimal-t4-verifier-kernel/artifacts/trace_llama_bench_T8.stderr
```

Parsed summary:

```text
T,avg_ns,avg_ms,total_ratio,avg_ts,function,call_count,call_ratio,last_n,last_bs,last_nrc
1,5421086333,5421.086,1.000,0.184465,ggml_vec_dot_q4_0_q8_0,2719744,1.000,11008,0,1
2,10638251863,10638.252,1.962,0.188001,ggml_vec_dot_q4_0_q8_0,5387264,1.981,11008,0,1
4,21090734440,21090.734,3.890,0.189657,ggml_vec_dot_q4_0_q8_0,10722304,3.942,11008,0,1
8,43073940247,43073.940,7.946,0.185727,ggml_vec_dot_q4_0_q8_0,21392384,7.866,11008,0,1
```

## Interpretation

This trace resolves the main ambiguity left by the previous prompt-pass run.
For this Q4_0 model and fresh traced build, T>1 does not primarily go through a
RISC-V `16x1` repack GEMV/GEMM path. It calls the single-RHS Q4_0 x Q8_0
vec-dot path with `nrc=1`, and the call count grows nearly linearly with T.

This is stronger than timing-only evidence. It supports:

```text
current path classification: repeated_t1
next gate: ggml-level C_old(T) microbenchmark
then: minimal T4 verifier microkernel
```

It still does not prove full-system GO. The next required evidence is
ggml-level C_old(T), followed by C_new(4) correctness and performance.
