# Curve Robustness

Date: 2026-06-17 Asia/Shanghai

Inputs:

- `../06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv`
- `../06-16-post-direct-t4-go-nogo/results/synthetic_workingset_sweep.csv`
- `../06-16-post-direct-t4-go-nogo/results/variant_timing.csv`
- `results/remote_claude_critique/rtile_ttile_rows128_r3.csv`
- `results/remote_claude_critique/rtile_ttile_rows2048_r3.csv`
- `scripts/resolve_claude_critique.py`

Output:

- `results/curve_robustness_matrix.csv`

## Remote Run

Remote host:

```text
rvv / ubuntu / Linux 6.12.23 / riscv64
```

Safety preflight:

```text
load average: 0.00, 0.01, 0.00
64 CPUs
121 GiB memory, 119 GiB available
```

Build/source:

```text
source tree: /home/ubuntu/vericurve-rv-lab/llama.cpp
commit: e36a602ba38a26206c749ba4fb5dcf481bfd92db
build: /home/ubuntu/vericurve-rv-lab/llama.cpp/build-vericurve
GGML_RVV=ON
GGML_CPU_REPACK=ON
GGML_BLAS=OFF
GGML_NATIVE=OFF
```

Command shape:

```text
OMP_NUM_THREADS=1 nice -n 10 timeout 600 \
  /home/ubuntu/vericurve-rv-lab/post-direct-t4/bench_rtile_ttile_kernel \
  11008 <rows> 3 1
```

Rows tested:

```text
128
2048
```

No rebuild, no sudo, no source mutation.

## Result

| case | rows | C_best_T1 | C_best_T4 | T4/T1 | winner T1 | winner T4 | speedup vs old T4 | conclusion |
|---|---:|---:|---:|---:|---|---|---:|---|
| current_rows512_q4_0_x_q8_0_best_curve | 512 | 12.024000 | 16.826000 | 1.399368 | old_vecdot_nrc1 | R8_rowblocked_weights_total | 2.857837 | scoped core pass |
| remote_shaped_rows128_q4_0_x_q8_0 | 128 | 2.996372 | 5.097000 | 1.701057 | old_vecdot_nrc1 | R8_Layout2_rowblocked_weights | 2.103349 | pass |
| remote_shaped_rows2048_q4_0_x_q8_0 | 2048 | 25.992796 | 73.802000 | 2.839325 | old_vecdot_nrc1 | R8_Layout2_rowblocked_weights | 1.410038 | weak |

The old path working-set sweep remains near linear at T=4:

```text
rows=32:   old T4/T1 = 4.079
rows=128:  old T4/T1 = 3.995
rows=512:  old T4/T1 = 4.000
rows=2048: old T4/T1 = 4.005
```

## Gate

Status: SCOPED.

Passes:

- The core rows=512 Q4_0 x Q8_0 case remains strong: `T4/T1 = 1.399`.
- A smaller rows=128 shaped run also passes: `T4/T1 = 1.701`.

Fails for broad claim:

- Larger rows=2048 shaped run degrades to `T4/T1 = 2.839`.
- No alternate quant shaped run has been measured.
- No real 7B-layer-specific shaped run has been measured beyond the synthetic
  `n=11008` harness.

Interpretation:

Do not claim broad LLM speedup or broad model-size robustness yet. The safe
paper scope is:

```text
Q4_0 x Q8_0 RVV verifier curve shaping for the measured rows=512 regime,
with evidence that the benefit degrades for a larger rows=2048 working set.
```

The next useful robustness step is not another controller replay; it is a
targeted shaped sweep for a realistic layer/quant case, or an explanation of
why the paper intentionally scopes to the current working-set regime.
