# pro3 Guidance Summary

`doc/pro3.md` interprets the previous round as a positive turning point:

```text
VeriCurve-RV should continue.
The mainline is no longer T-visible kernels.
The mainline is RTile x TTile curve-shaping verifier kernels plus
curve-aware speculation.
```

## Main Thesis

```text
T visibility alone is insufficient.
Curve shaping requires a two-dimensional verifier microkernel that jointly
blocks output rows and token positions.
```

Paper-facing sentence:

```text
VeriCurve-RV reshapes the speculative verification cost curve with RTile x
TTile low-bit RVV verifier microkernels, then lets the runtime select verifier
variant and draft budget based on the new curve.
```

## Current Status

```text
GO-characterization: yes
GO-curve-shaping-kernel: STRONG GO
GO-schedule-variant-mechanism: GO
GO-cache-mainline: no, supporting only
GO-controller-next-step: yes
FULL PAPER GO: conditional on controller / draft / acceptance
```

## Next Round

This task should measure:

```text
C_verify_best(T)
C_draft(d)
acceptance(d)
J(d)
minimal controller Go/No-Go
```

It should not keep optimizing the kernel before answering whether the new curve
creates meaningful speculation-budget choices.
