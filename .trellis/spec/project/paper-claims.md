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

## Current Claim Boundary: A-Level Search After Claude Critique

As of task `.trellis/tasks/06-16-real-online-controller-validation`, the safe
Version B framing is only a conservative fallback boundary:

```text
Version B: curve-shaping systems paper
```

It is not a current instruction to write the paper. The replay-only A-level
innovation search found no mechanism-level candidate from existing evidence,
but that conclusion was provisional until a real RVV T8 gate was run.

Allowed current fallback claim:

```text
RTile x TTile RVV verification reshapes C_verify(T), and the shaped curve
changes speculation viability: code/rag/structured shift from old-curve
best d=0 to shaped-curve best d=3, while chat/chat_low remain d=0.
```

Current fallback phrasing before the real T8 result:

```text
curve-gated speculation over {d=0,d=3}
```

Avoid current overclaims:

- Do not call the current controller a strong new adaptive algorithm.
- Do not claim curve-aware selected-only control beats goodput-only by a
  meaningful margin; current advantage is about `0.91%`, so this is a tie.
- Do not claim broad model/quant robustness; rows2048 real T8 is a near-pass,
  not a broad cross-quant/model result.

Replay-only A-level decision, now superseded by the real T8 gate:

```text
A-level candidate found? NO  # provisional replay-only result
```

Current real RVV T8 verifier-plan decision:

```text
task: .trellis/tasks/06-17-real-rvv-t8-verifier-plan-gate
best rows512 real T8: native_T8_packed_rhs_rowblocked_weights, R=16
rows512 C8/C1 = 1.754
rows2048 C8/C1 = 2.130
multi-action oracle gain over {d0,d3} = 8.424949%
full-info myopic plan-aware advantage vs goodput-only = 22.259059%
existing selected-only two-action advantage vs goodput-only = 0.909599%
```

Allowed current mechanism claim:

```text
Real RVV verifier-plan synthesis can reshape C_verify(8) enough to make d7 and
multi-action speculation meaningful in replay.
```

Current boundary:

```text
mechanism gate: GO
paper/full online-controller gate: not complete
```

Do not write a paper or claim a selected-only online controller until a
low-observability/runtime controller recovers enough of the full-info
plan-aware gain without oracle access.
