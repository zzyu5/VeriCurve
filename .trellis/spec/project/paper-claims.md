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

## Current Claim Boundary: Claude Critique Resolution

As of task `.trellis/tasks/06-16-real-online-controller-validation`, the safe
paper version is:

```text
Version B: curve-shaping systems paper
```

Allowed current claim:

```text
RTile x TTile RVV verification reshapes C_verify(T), and the shaped curve
changes speculation viability: code/rag/structured shift from old-curve
best d=0 to shaped-curve best d=3, while chat/chat_low remain d=0.
```

Required phrasing:

```text
curve-gated speculation over {d=0,d=3}
```

Avoid current overclaims:

- Do not call the current controller a strong new adaptive algorithm.
- Do not claim multi-point control over `d={0,1,3,7}`; oracle gain from adding
  `d=1,d=7` is currently `0.000%`.
- Do not claim curve-aware selected-only control beats goodput-only by a
  meaningful margin; current advantage is about `0.91%`, so this is a tie.
- Do not claim broad model/quant robustness; rows=2048 shaped T4/T1 degraded
  to about `2.839`, and no cross-quant shaped case has been measured.
