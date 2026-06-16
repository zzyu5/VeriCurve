# Paper Claims and Evidence Rules

## Claims That Need Evidence

| Claim | Required evidence |
|---|---|
| Current llama.cpp/RVV T>1 path is weak or linear | Call trace, source-path audit, and `C_old(T)` measurements. |
| `C_verify(T)` has useful structure | CSV/JSON results for T list, plotted `C(T)/C(1)` and `C(T)/T`. |
| T-specialized kernels reshape the curve | Old-vs-new curve with same model, quantization, threads, machine, and build flags. |
| Fixed d mispredicts under drift | Workload-level and mixed-workload results against oracle. |
| Controller is useful beyond kernel speedup | Ablation: old/new kernels, fixed d, goodput-only adaptive, VeriCurve, oracle. |

## Claims to Avoid

- "We invented adaptive speculation."
- "We are the first hardware-aware speculation system."
- "This is just a faster RVV kernel."
- "Kernel selection by shape is the contribution."
- "The framework makes kernels easy to insert" as a core scientific claim.

## Required Distinctions

Use precise language:

- `measured`: backed by artifact and command.
- `inferred`: supported by measurements but not directly measured.
- `hypothesis`: planned explanation requiring future data.
- `fallback`: viable paper route if original speedup path is weak.

Do not present a planned kernel or controller as already validated.

