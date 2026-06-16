# VeriCurve-RV Trellis Spec Index

This Trellis spec captures the current project intent for VeriCurve-RV. It is a research-system project, not a frontend/backend web application.

## Project Packages

| Package | Purpose |
|---|---|
| [project](./project/index.md) | Research positioning, contribution boundary, and paper-level constraints. |
| [llamacpp-rvv](./llamacpp-rvv/index.md) | llama.cpp/RVV integration boundary, current-path audit, and shared `ssh rvv` safety rules. |
| [curve-system](./curve-system/index.md) | Curve profiler, verifier kernels, curve model, profile cache, and controller contracts. |
| [experiments](./experiments/index.md) | Go/No-Go experiment sequence, metrics, artifacts, and success/failure criteria. |

## Source Design Documents

The source design discussion lives under `VeriCurve-RV-design/`. Trellis spec should stay aligned with these files:

- `VeriCurve-RV-design/VeriCurve-RV-system-design.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/01_problem_and_positioning.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/02_core_concepts.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/03_system_architecture.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/04_curve_model_and_controller.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/05_kernel_design.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/06_experimental_plan.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/07_implementation_plan.md`

## Global Development Rules

1. Keep the single-paper prototype self-contained: llama.cpp/RVV characterization, minimal T-specialized kernels, controller, and evaluation.
2. Do not turn the work into a generic kernel framework, a generic adaptive speculation paper, or a TianchenRV-only kernel paper.
3. Persist every experiment result as a file with command, hardware, model, quantization, thread count, commit, and raw output.
4. Remote `rvv` is a shared machine. Use the safety rules in `llamacpp-rvv/remote-rvv-safety.md` before any build or benchmark.
5. When claiming performance, tie it to a concrete artifact: source commit, build command, model/quant, profiler command, CSV/JSON result, and remote machine state.

