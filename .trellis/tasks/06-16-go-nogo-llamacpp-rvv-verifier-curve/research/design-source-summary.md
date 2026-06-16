# Design Source Summary

This task follows the VeriCurve-RV design documents under `VeriCurve-RV-design/`.

## Core Thesis

VeriCurve-RV studies RISC-V/RVV low-bit speculative inference through the verifier cost curve:

```text
T = target verifier token-width = 1 + draft tokens d
C_verify(T) = target verifier cost for T token positions
C_draft(d) = draft cost
E_accept(d) = expected accepted draft tokens
```

The key claim is that the optimal draft budget is a joint function of `C_verify(T)`, `C_draft(d)`, and acceptance drift. Verifier cost must not be treated as a backend black-box constant.

## Minimal System

1. Curve profiler for `C_verify(T)`, `C_draft(d)`, and acceptance.
2. Lightweight curve model.
3. Minimal T-specialized RVV verifier kernels.
4. Curve-aware speculation controller in llama.cpp.

## Go/No-Go Sequence

1. Audit current llama.cpp/RVV path for T in `{1,2,4,8}`.
2. Measure `C_old(T)`.
3. Implement or plan a minimal T4 verifier kernel.
4. Compare `C_new(T)` to `C_old(T)`.
5. Measure `C_draft(d)` and acceptance drift.

## Direction Criteria

- Strongest: common T values show sweet spots or rebound.
- Viable: curves are monotonic but slope drifts across quantization, hardware, or workload.
- Weak: curves stay near-linear and T-specialized kernels cannot compress T4/T8 cost.
- Fallback: characterization paper about why current RVV low-bit paths are not speculation-friendly.

## Boundary

This is not a generic adaptive speculation paper, not a shape-conditioned kernel-selection paper, and not a pure RVV kernel paper. The kernel exists to reshape `C_verify(T)` so the controller has meaningful decisions to make.

