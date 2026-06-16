# Local llama.cpp Path Audit

## Snapshot

Local source tree:

```text
/home/kingdom/phdworks/llama.cpp
```

Local branch and commit:

```text
branch: master
HEAD: 6eab47181cbd3532c88a105682b81b4729ab809b
date: 2026-06-15 10:11:59 +0300
subject: wasm : fix fallback symbol collision (#24639)
```

Remote HEAD checked with `git ls-remote origin HEAD`:

```text
e36a602ba38a26206c749ba4fb5dcf481bfd92db
```

Local working tree status:

```text
git status --short: empty
```

Conclusion: local checkout is clean but behind upstream HEAD. Remote `rvv` clone was therefore used for latest-source confirmation.

## Relevant Source Paths

RISC-V/RVV build and backend selection:

```text
ggml/CMakeLists.txt
ggml/src/CMakeLists.txt
ggml/src/ggml-cpu/CMakeLists.txt
ggml/src/ggml-cpu/ggml-cpu.c
ggml/src/ggml-cpu/arch/riscv/quants.c
ggml/src/ggml-cpu/arch/riscv/repack.cpp
ggml/src/ggml-cpu/repack.cpp
```

Speculative decoding:

```text
examples/speculative/speculative.cpp
common/speculative.cpp
common/speculative.h
common/sampling.cpp
tools/server/server-context.cpp
```

## Current Path Evidence

The current RISC-V low-bit vec-dot implementations are mostly single-result vec-dot functions. In `ggml/src/ggml-cpu/arch/riscv/quants.c`, `ggml_vec_dot_q4_0_q8_0` and many other low-bit vec-dot functions assert:

```text
assert(nrc == 1)
```

This is evidence that the direct RISC-V vec-dot path is not itself a multi-RHS verifier kernel.

However, `ggml/src/ggml-cpu/repack.cpp` contains RISC-V-specific repack traits such as:

```text
q4_0_16x1_q8_0
q4_K_16x1_q8_K
q8_0_16x1_q8_0
```

The trait selection checks `ggml_cpu_has_riscv_v()` and, under `__riscv_zvfh`, returns the `16x1` traits when `__riscv_vlenb() * 8 == 256` and the relevant tensor dimension is divisible by 16.

This means current path classification cannot be decided by vec-dot source alone:

- direct `arch/riscv/quants.c` vec-dot: looks like `repeated_t1` building block;
- repack path: may be an existing `generic_batch_path` or limited multi-row path for compatible shapes.

## Speculative Decoding Mapping

`examples/speculative/speculative.cpp` builds a target batch containing drafted tokens and calls:

```text
llama_decode(ctx_tgt, batch_tgt)
```

It tracks target batch indices through `i_batch_tgt`. The server path similarly verifies draft tokens using:

```text
common_sampler_sample_and_accept_n(..., slot.spec_i_batch, slot.spec_draft)
```

This confirms the VeriCurve-RV T variable maps naturally to target verification batch width:

```text
T = n_draft + 1
```

## Preliminary Classification

Current path label from source only:

```text
unresolved
```

Reason:

`arch/riscv/quants.c` strongly suggests single-output low-bit vec-dot kernels, but RISC-V `16x1` repack GEMV/GEMM exists and may be selected on the actual RVV host. A measured call trace or C_old(T) run is required.

