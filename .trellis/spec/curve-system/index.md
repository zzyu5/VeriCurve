# Curve System Spec

## Pre-Development Checklist

- Identify which curve is being measured: microkernel, layer, or model-level.
- Record T, d, quantization, model, backend commit, thread count, and hardware.
- Keep profiler, kernel, and controller artifacts separate until each has evidence.

## Guidelines

| Guide | Description |
|---|---|
| [profiler](./profiler.md) | `C_verify(T)`, `C_draft(d)`, and profile cache contract. |
| [kernel-design](./kernel-design.md) | T-specialized RVV verifier kernel requirements. |
| [controller](./controller.md) | Curve-aware draft-budget selection logic. |

## Quality Check

- Any curve result must include both total latency and per-position latency.
- Any new kernel must be compared against the old path under identical conditions.
- Any controller result must include selected d/T, predicted score, actual acceptance, and fallback status.

