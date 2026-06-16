# Current llama.cpp/RVV Path Audit

Experiment 0 must answer this before new kernels:

```text
When T in {1,2,4,8,16}, does current llama.cpp/RVV verification use a true multi-RHS path, a generic batch matmul, or repeated single-RHS vec_dot work?
```

## Required Steps

1. Identify the exact llama.cpp commit.
2. Identify RVV build flags and whether RVV code paths are enabled.
3. Locate low-bit matmul / vec-dot implementation files.
4. Locate speculative decoding control flow and how draft length maps to target verification batch/T.
5. Add or use low-overhead tracing for kernel calls if source reading is not enough.
6. Measure or estimate `C_old(T)` with identical model, quantization, and thread count.
7. After a direct T4 failure, audit existing repack/llamafile/tinyBLAS/16x1
   paths before building another custom kernel.

## Required Artifacts

```text
notes/current_llamacpp_rvv_path.md
artifacts/call_trace_T1.txt
artifacts/call_trace_T4.txt
results/C_old_verify.csv
```

## Low-Overhead Trace Contract

When source reading and model-level timing are not enough, add a trace mode
that counts calls without printing inside hot loops.

Suggested environment gate:

```text
GGML_VERICURVE_TRACE=1
```

Minimum counters:

```text
function_name
call_count
n
nr
nc
nrc
bs
T or prompt/token width when available
total_time_ns if the timing hook is cheap
```

Trace must distinguish:

```text
ggml_vec_dot_*_q8_*       single-RHS vec-dot path
ggml_gemv_*_16x1_*        RISC-V repack GEMV path
ggml_gemm_*_16x1_*        RISC-V repack GEMM path
llamafile / tinyBLAS      non-target path for this RVV evidence
scalar/fallback           fallback path
```

## Repack Path Audit Contract

For post-direct-T4 work, record these fields for every relevant low-bit
repack/GEMV/GEMM path:

```text
path_name
source_file
quant_type
supports_rvv
requires_zvfh
requires_vlen_bits
shape_alignment
layout_requirement
build_flag_requirement
guard_result
reason_not_selected
entered_by_prompt_T4
entered_by_microbench_T4
```

The audit must answer whether these paths exist and are relevant:

```text
q4_0_16x1_q8_0
q4_K_16x1_q8_K
q8_0_16x1_q8_0
llamafile / tinyBLAS alternatives
```

If the hardware or build does not satisfy a guard, record that as an explicit
No-Go reason for the existing-repack branch instead of silently falling back to
custom code.

## Current rvv Repack Finding

The current `rvv` host reports:

```text
__riscv_vector = 1
__riscv_zvfh = 1
vlen_bits = 128
```

The current llama.cpp RISC-V `16x1` repack selector requires:

```text
__riscv_zvfh
ggml_cpu_has_riscv_v()
__riscv_vlenb() * 8 == 256
cur->ne[1] % 16 == 0
CPU_REPACK tensor placement for src0
```

Therefore the existing `q4_0_16x1_q8_0`, `q4_K_16x1_q8_K`, and
`q8_0_16x1_q8_0` paths exist and compile, but are not selected on the current
VLEN=128 machine. Do not assume upstream 16x1 repack is the measured T4 path
unless a future trace shows nonzero repack GEMV/GEMM counters.

Do not emit one log line per inner-loop iteration. Aggregate counts and dump
once at process exit or benchmark end.

## Classification

Use one of these labels:

- `multi_rhs_present`: T>1 has a true multi-RHS or batch-efficient low-bit path.
- `generic_batch_path`: T>1 goes through a general path, but not clearly repeated T1.
- `repeated_t1`: T>1 behaves like repeated single-token verification.
- `unresolved`: source or measurement evidence is insufficient.

Do not use "current path is bad" without one of these labels and supporting evidence.

## Trace Go/No-Go

```text
GO-T4-kernel:
  T>1 low-bit call counts scale approximately with T,
  or trace shows nrc == 1 / single-RHS vec-dot dominates.

CONDITIONAL:
  trace enters repack GEMV/GEMM, but measured C_old(T) remains near-linear.
  Continue with a ggml-level microbenchmark before implementing T4.

NO-GO for T4 kernel gap:
  trace shows an efficient multi-RHS low-bit path and microbenchmark
  C_old(4) < 2.2 * C_old(1).
```
