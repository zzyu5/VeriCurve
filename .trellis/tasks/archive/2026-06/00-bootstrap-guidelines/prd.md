# Bootstrap Task: VeriCurve-RV Trellis Spec

## Goal

Initialize Trellis for the VeriCurve-RV third-topic project and replace the generic frontend/backend template with project-specific research-system spec.

## Completed Spec Shape

- [x] Project positioning and paper-claim boundaries
- [x] Minimal scope and deliverables
- [x] llama.cpp/RVV current-path audit rules
- [x] Shared `ssh rvv` safety protocol
- [x] Curve profiler, kernel, and controller contracts
- [x] Go/No-Go experiment criteria
- [x] Artifact and workload conventions

## Source Documents

The spec was derived from:

- `VeriCurve-RV-design/VeriCurve-RV-system-design.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/01_problem_and_positioning.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/02_core_concepts.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/03_system_architecture.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/04_curve_model_and_controller.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/05_kernel_design.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/06_experimental_plan.md`
- `VeriCurve-RV-design/VeriCurve-RV-design/07_implementation_plan.md`

## Notes

The default Trellis frontend/backend template was intentionally removed because this repository is not a web app. Future tasks should select context from `project`, `llamacpp-rvv`, `curve-system`, and `experiments`.

