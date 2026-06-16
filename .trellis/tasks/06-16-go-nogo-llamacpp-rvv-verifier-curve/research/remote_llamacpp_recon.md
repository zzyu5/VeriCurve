# Remote llama.cpp Reconnaissance

## Remote Work Directory

```text
/home/ubuntu/vericurve-rv-lab/llama.cpp
```

The directory was created specifically for VeriCurve-RV. No TianchenRV directory was modified.

## Clone

Command:

```bash
cd "$HOME/vericurve-rv-lab"
nice -n 10 timeout 180 git clone --depth 1 https://github.com/ggml-org/llama.cpp.git
```

Result:

```text
clone completed
HEAD: e36a602ba38a26206c749ba4fb5dcf481bfd92db
date: 2026-06-15 18:07:14 +0200
subject: mtmd: fix miscounting n_tokens (#24656)
git status --short: empty
```

## Toolchain

```text
git version 2.43.0
cmake version 3.28.3
g++ (Ubuntu 14.2.0-4ubuntu2~24.04.1) 14.2.0
Ubuntu clang version 18.1.3 (1ubuntu1)
ninja: not installed
```

## Configure

Command:

```bash
cd "$HOME/vericurve-rv-lab/llama.cpp"
nice -n 10 timeout 180 cmake -S . -B build-vericurve \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_RVV=ON \
  -DGGML_NATIVE=OFF \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=ON \
  -DLLAMA_BUILD_SERVER=OFF
```

Key output:

```text
CMAKE_SYSTEM_PROCESSOR: riscv64
GGML_SYSTEM_ARCH: riscv64
Including CPU backend
riscv64 detected
Adding CPU backend variant ggml-cpu: -march=rv64gcv_zfh_zvfh_zicbop_zihintpause;-mabi=lp64d
ggml version: 0.15.1
ggml commit: e36a602
Configuring done
Build files have been written to: /home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve
```

This confirms latest llama.cpp can configure native RVV backend on the shared `rvv` host.

## Source Confirmation on Latest Remote HEAD

Remote `grep` confirmation found:

```text
ggml/src/ggml-cpu/arch/riscv/quants.c:222 void ggml_vec_dot_q4_0_q8_0(...)
ggml/src/ggml-cpu/arch/riscv/quants.c:228 assert(nrc == 1)
```

and many other low-bit RISC-V vec-dot functions with `assert(nrc == 1)`.

Remote `grep` also found the RISC-V repack path:

```text
ggml/src/ggml-cpu/repack.cpp:4561 instances for RISC-V
ggml/src/ggml-cpu/repack.cpp:4566 q4_0_16x1_q8_0
ggml/src/ggml-cpu/repack.cpp:4593 case 256: if (cur->ne[1] % 16 == 0) return &q4_0_16x1_q8_0
ggml/src/ggml-cpu/repack.cpp:4620 q4_K_16x1_q8_K
ggml/src/ggml-cpu/repack.cpp:4714 q8_0_16x1_q8_0
```

Speculative decoding confirmation found:

```text
examples/speculative/speculative.cpp:195 int n_draft = params.speculative.draft.n_max
examples/speculative/speculative.cpp:610 llama_decode(ctx_tgt, batch_tgt)
common/sampling.cpp:621 common_sampler_sample_and_accept_n(...)
tools/server/server-context.cpp:3475 const size_t n_draft = slot.spec_draft.size()
tools/server/server-context.cpp:3485 common_sampler_sample_and_accept_n(...)
```

## Build Attempt

Command:

```bash
cd "$HOME/vericurve-rv-lab/llama.cpp"
nice -n 10 timeout 600 cmake --build build-vericurve --target llama-bench -j1
```

Result:

```text
exit code: 124
reason: timeout after 600 seconds
```

Important build progress before timeout:

```text
[11%] Built target ggml-cpu
[13%] Built target ggml
[21%] Building CXX object src/CMakeFiles/llama.dir/llama-model-loader.cpp.o
```

Produced shared libraries:

```text
build-vericurve/bin/libggml-base.so -> libggml-base.so.0
build-vericurve/bin/libggml-cpu.so -> libggml-cpu.so.0
build-vericurve/bin/libggml.so -> libggml.so.0
```

Key warning categories:

```text
ISO C does not support _Float16 before C23
strict-aliasing warnings in RVV fp16 paths
maybe-uninitialized warnings in vec.cpp RVV paths
missing-prototype warnings in arch/riscv/quants.c
```

No build error occurred before timeout. Full RTK-captured command output was reported at:

```text
~/.local/share/rtk/tee/1781542013_ssh_-o_BatchMode_yes_-o_ConnectTimeout_1.log
```

## Build Feasibility Interpretation

The RVV backend and RISC-V repack sources compile successfully through `ggml-cpu` under `-j1`. Full `llama-bench` build is feasible but too slow for a cautious 600-second single-core probe. A follow-up can continue from the partial build with a longer timeout or a carefully chosen low parallelism level if the remote remains idle and the user agrees.

## Later Low-Risk Reuse: Existing RVV Integration Tree

After the fresh `~/vericurve-rv-lab/llama.cpp` build timed out before
`llama-bench`, a cheaper path was found: an existing remote tree with an
RVV-only CPU build and no BLAS backend.

Candidate trees inspected:

```text
/home/ubuntu/llama_integ
/home/ubuntu/llama_integ_control_repackON
/home/ubuntu/llama_integ_canary_repackON
/home/ubuntu/workspace/workspace3/llama.cpp
```

The `control_repackON` and `canary_repackON` trees printed
`[TCRV_Q4_INTEG]` instrumentation messages and were not used for the benchmark.
The workspace3 tree reported OpenBLAS and was rejected as RVV evidence.

Selected tree:

```text
/home/ubuntu/llama_integ
```

Relevant cache facts:

```text
GGML_BLAS=OFF
GGML_CPU=ON
GGML_CPU_REPACK=ON
GGML_NATIVE=ON
GGML_RVV=ON
```

Version:

```text
build commit: 6eab471
compiler: GNU 14.2.0 for Linux riscv64
```

Only the missing benchmark target was built:

```bash
cd "$HOME/llama_integ"
nice -n 10 timeout 600 cmake --build build --target llama-bench -j1
```

Result:

```text
[100%] Built target llama-bench
```

Device/backend check:

```text
llama-bench --list-devices: Available devices: (none)
benchmark rows: backends = CPU, cpu_info = CPU
```

This provided the bounded `C_old(T)` measurement path recorded in:

```text
.trellis/tasks/06-16-go-nogo-llamacpp-rvv-verifier-curve/research/C_old_prompt_T_rvv_threads1.md
```
