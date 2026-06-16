# Project Spec: VeriCurve-RV

## Pre-Development Checklist

- Confirm whether the task is research planning, llama.cpp/RVV code work, remote measurement, or paper-writing support.
- Read the relevant design source under `VeriCurve-RV-design/` before changing spec or experiment plans.
- Preserve the main thesis: verifier cost curve `C_verify(T)` is a decision input for speculative decoding.
- Keep IntentIR and TianchenRV as background only unless the task explicitly asks for integration.
- For any remote work, load `../llamacpp-rvv/remote-rvv-safety.md` first.

## Guidelines

| Guide | Description |
|---|---|
| [positioning](./positioning.md) | Research thesis, non-goals, and relation to prior topics. |
| [scope](./scope.md) | Minimal deliverables, allowed scope, and fallback boundaries. |
| [paper-claims](./paper-claims.md) | Claims that must be supported, and claims to avoid. |

## Quality Check

- A task result should say whether it advances C1 characterization, C2 curve model, C3 curve-shaping kernels, or C4 controller.
- Any Go/No-Go statement must name the exact criterion it uses.
- Any paper-facing statement must distinguish measured evidence, planned experiment, and hypothesis.

