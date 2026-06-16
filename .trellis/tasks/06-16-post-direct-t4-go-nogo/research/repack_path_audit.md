# A1 Repack / 16x1 Path Audit

## Remote Tree

```text
path: /home/ubuntu/vericurve-rv-lab/llama.cpp
commit: e36a602ba38a26206c749ba4fb5dcf481bfd92db
build: /home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve
remote dirty files:
  ggml/src/ggml-cpu/arch/riscv/quants.c
  ggml/src/ggml-cpu/repack.cpp
dirty state reason:
  previous low-overhead VeriCurve trace instrumentation
```

The dirty files were not reverted or edited in this task.

## Build Flags

The `ggml-cpu` compile commands include:

```text
-DGGML_USE_CPU_REPACK
-DGGML_USE_LLAMAFILE
-DGGML_USE_OPENMP
-march=rv64gcv_zfh_zvfh_zicbop_zihintpause
-mabi=lp64d
```

`CMakeCache.txt` contains:

```text
GGML_CPU_REPACK:BOOL=ON
GGML_CPU_ALL_VARIANTS:BOOL=OFF
```

So the build does contain the repack code and `__riscv_zvfh` code paths.

## Hardware Probe

A task-local probe was compiled and run on `rvv` with:

```text
cc -O2 -march=rv64gcv_zfh_zvfh_zicbop_zihintpause -mabi=lp64d vlen_probe.c -o vlen_probe
```

Output:

```text
__riscv_vector=1
__riscv_zvfh=1
vlen_bits=128
```

This is decisive for the current llama.cpp selector: the RISC-V `16x1` repack
traits only return for `__riscv_vlenb() * 8 == 256`; the `128` case is a TODO
that breaks without returning a trait.

## Paths Found

The following functions and traits exist:

```text
q4_0_16x1_q8_0:
  ggml/src/ggml-cpu/repack.h
  ggml/src/ggml-cpu/repack.cpp
  ggml/src/ggml-cpu/arch/riscv/repack.cpp

q4_K_16x1_q8_K:
  ggml/src/ggml-cpu/repack.h
  ggml/src/ggml-cpu/repack.cpp
  ggml/src/ggml-cpu/arch/riscv/repack.cpp

q8_0_16x1_q8_0:
  ggml/src/ggml-cpu/repack.h
  ggml/src/ggml-cpu/repack.cpp
  ggml/src/ggml-cpu/arch/riscv/repack.cpp
```

The relevant selector creates RISC-V tensor traits under `__riscv_zvfh`:

```text
tensor_traits<block_q4_0, 1, 16, GGML_TYPE_Q8_0> q4_0_16x1_q8_0
tensor_traits<block_q4_K, 1, 16, GGML_TYPE_Q8_K> q4_K_16x1_q8_K
tensor_traits<block_q8_0, 1, 16, GGML_TYPE_Q8_0> q8_0_16x1_q8_0
```

For Q4_0, Q4_K, and Q8_0, the RISC-V selector checks:

```text
ggml_cpu_has_riscv_v()
__riscv_zvfh
__riscv_vlenb() * 8 == 256
cur->ne[1] % 16 == 0
```

On the current `rvv`, the VLEN guard fails:

```text
current vlen_bits = 128
selector case 128 = TODO / break
```

## Buffer and Op Support Conditions

`CPU_REPACK` is an extra CPU buffer type, not the default model buffer. It is
registered only when `GGML_USE_CPU_REPACK` is compiled:

```text
ggml_backend_cpu_get_extra_buffer_types()
  -> ggml_backend_cpu_repack_buffer_type()
```

The repack extra buffer supports an op only when:

```text
op == GGML_OP_MUL_MAT or GGML_OP_MUL_MAT_ID
src0 has a buffer
src0 buffer type is CPU_REPACK
src0 has an optimal repack type
src1 is host-compatible
src1 type is GGML_TYPE_F32
```

The default `llama_model_default_params()` sets:

```text
tensor_buft_overrides = nullptr
```

Therefore a normal `llama-bench` run does not force weights into `CPU_REPACK`.
The command-line path exists through tensor buffer override parsing, but it was
not used in the previous prompt-pass traces.

## Previous Trace Evidence

The inherited T1/T2/T4/T8 trace showed only:

```text
function = ggml_vec_dot_q4_0_q8_0
last_nrc = 1
```

No nonzero `ggml_gemv_q4_0_16x1_q8_0` or
`ggml_gemm_q4_0_16x1_q8_0` trace rows appeared.

Key trace rows:

```text
T=1 call_count=2719744 ratio=1.000 last_n=11008 last_nrc=1
T=2 call_count=5387264 ratio=1.981 last_n=11008 last_nrc=1
T=4 call_count=10722304 ratio=3.942 last_n=11008 last_nrc=1
T=8 call_count=21392384 ratio=7.866 last_n=11008 last_nrc=1
```

## Why Current T4 Did Not Enter Existing Repack

There are two independent blockers:

1. Default model loading did not force the relevant weights into `CPU_REPACK`,
   so the repack extra buffer was not active for the measured prompt path.
2. Even if `CPU_REPACK` is forced, the current `rvv` has VLEN=128, while the
   RISC-V `16x1` selector returns traits only for VLEN=256.

The second blocker is stronger: on this hardware, the existing upstream
`16x1` repack branch is not selectable without adding a VLEN=128 variant or
changing the selector and kernel implementation.

## A1 Decision

```text
GO-custom-RT-kernel
```

Rationale:

```text
Existing repack paths are real and compile, but they are unavailable on the
current rvv because the selector's RVV guard requires VLEN=256 and the machine
reports VLEN=128. The current prompt path also used default tensor placement
instead of CPU_REPACK. Therefore existing repack cannot explain or fix the
near-linear T4 curve on this machine as-is.
```

The next valid branch is a custom `RTile x TTile` / layout-aware harness that
targets VLEN=128 explicitly, not another direct R1T4 wrapper.
