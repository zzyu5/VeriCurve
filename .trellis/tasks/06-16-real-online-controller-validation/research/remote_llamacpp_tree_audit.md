# Remote llama.cpp Tree Audit

Remote tree:

```text
/home/ubuntu/vericurve-rv-lab/llama.cpp
```

Commit:

```text
e36a602ba38a26206c749ba4fb5dcf481bfd92db
```

Dirty state:

```text
M ggml/src/ggml-cpu/arch/riscv/quants.c
M ggml/src/ggml-cpu/repack.cpp
M examples/lookup/lookup-stats.cpp
```

The first two dirty changes are prior VeriCurve trace instrumentation:

```text
GGML_VERICURVE_TRACE records ggml_vec_dot_q4_0_q8_0 calls.
GGML_VERICURVE_TRACE records q4_0/q8_0 repack gemv/gemm calls.
```

The `lookup-stats.cpp` dirty change is this task's patch:

```text
VERICURVE_LOOKUP_TRACE_CSV records per-step lookup drafted/accepted counts.
VERICURVE_LOOKUP_ALIGNED_TRACE_CSV records same-position candidate d=0/1/3/7 counts.
VERICURVE_LOOKUP_STATE_EQ_CSV records d0-stepwise vs d3-committed pseudo/cache hashes.
VERICURVE_LOOKUP_POSITION_COMPLETE_CSV records teacher-forced per-position candidates.
```

Build directory:

```text
/home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve
```

Backend flags from `CMakeCache.txt`:

```text
GGML_RVV=ON
GGML_CPU=ON
GGML_CPU_REPACK=ON
GGML_BLAS=OFF
GGML_NATIVE=OFF
```

Existing executable:

```text
build-vericurve/bin/llama-bench
```

Relevant CMake targets:

```text
llama-lookup
llama-lookup-create
llama-lookup-merge
llama-lookup-stats
llama-speculative
llama-speculative-simple
```

Model availability:

```text
llama.cpp/models contains mostly vocab/test GGUF files, not full inference models.
Reusable full models exist outside the task tree:
  /home/ubuntu/llama-2-7b-chat.Q4_0.gguf
  /home/ubuntu/workspace/workspace3/DeepSeek-R1-Distill-Llama-8B-GGUF/*.gguf
```

Selected first integration route:

```text
examples/lookup / llama-lookup
```

Reason:

```text
It is a real llama.cpp prompt-lookup speculative path, uses ngram-style draft
tokens, and does not require a separate draft model. This matches the cheap
draft source used in the offline feasibility task better than two-model
speculative-simple.
```

Safety note:

```text
Do not overwrite or clean the dirty tree. The lookup trace changes are captured
in patches/llamacpp_acceptance_trace.patch and
patches/aligned_candidate_trace.patch, with pro7 additions in
patches/pseudo_state_hash.patch and patches/position_complete_trace.patch.
Prefer single-target -j1 builds and short runs.
```

pro7 update:

```text
lookup-stats.cpp diff stat: 298 insertions
rebuilt target: llama-lookup-stats
build command: nice -n 10 timeout 600 cmake --build build-vericurve --target llama-lookup-stats -- -j1
run command shape: nice -n 10 timeout 120 llama-lookup-stats ... -c 64 -t 1 -b 64 -ub 64 --spec-draft-n-max 3
residual process check: no llama/build process matched except the pgrep command itself
```
