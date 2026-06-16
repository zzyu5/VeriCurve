# Research Positioning

VeriCurve-RV studies speculative decoding on RISC-V/RVV low-bit LLM inference through the verifier cost curve:

```text
T = target verifier token-width = 1 + draft token count d
C_verify(T) = target verifier cost for T token positions
C_draft(d) = draft cost
E_accept(d) = expected accepted draft tokens
```

The core thesis is:

> The optimal draft budget is not determined by acceptance rate alone. It depends on `C_verify(T)`, `C_draft(d)`, workload acceptance drift, and RVV-specific kernel behavior such as VLEN, LMUL, register pressure, quantization layout, and cache behavior.

## What This Project Is

- A verifier-cost-curve characterization project for llama.cpp/RVV.
- A lightweight model of why `C_verify(T)` changes across T, quantization, RVV configuration, and kernel design.
- A minimal curve-shaping prototype using T-specialized RVV verifier kernels.
- A curve-aware speculation controller that chooses `d` from a small candidate set.

## Contribution Spine

Keep the single-paper contribution order narrow:

```text
C1. Characterization:
    show the current llama.cpp/RVV verifier curve and identify whether T>1
    uses repeated single-RHS work, a generic batch path, or a true multi-RHS
    low-bit path.

C2. Curve-shaping microkernel:
    implement the smallest T-specialized RVV verifier kernel that can change
    C_verify(T), starting with Q4_0 x Q8_0 T4 unless evidence selects another
    low-bit path.

C3. Curve model:
    explain the resulting sweet spot or cliff using reuse, VLEN/LMUL,
    accumulator pressure, quantization layout, and cache/memory behavior.

C4. Curve-aware speculation:
    use C_verify(T), C_draft(d), and acceptance drift to choose draft budget d.
```

Do not start with a broad scheduler or controller claim. If the old curve is
near-linear and no new kernel has reshaped it, there is no useful curve for a
controller to exploit yet.

## What This Project Is Not

- Not a generic kernel-centered inference framework.
- Not a paper about making llama.cpp easier to plug kernels into.
- Not shape-conditioned kernel selection where shape is already fixed and the runtime chooses a tile.
- Not generic adaptive speculation based only on goodput or acceptance rate.
- Not a pure RVV kernel paper, even if a T4/T8 kernel is required as an enabling artifact.
- Not a paper that depends on full TianchenRV automation.

## Required Storyline

The story should remain:

```text
draft length d changes verifier token-width T
T changes verifier cost curve C_verify(T)
microkernel and RVV design can reshape C_verify(T)
C_verify(T), C_draft(d), and acceptance drift jointly determine the best d
```

If a task does not fit this chain, it is probably outside the third-topic core.
