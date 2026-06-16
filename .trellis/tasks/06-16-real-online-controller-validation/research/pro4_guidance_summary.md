# pro4 Guidance Summary

`doc/pro4.md` says the project should continue, but the next decisive question
has changed:

```text
Kernel feasibility is no longer the main blocker.
The next blocker is whether real llama.cpp acceptance traces and an online
controller can turn the conditional offline result into a full-system result.
```

Inherited labels:

```text
GO-characterization: yes
GO-current-path-gap: yes
NO-GO-direct-R1T4: yes
GO-RTile x TTile-curve-shaping: STRONG GO
GO-runtime-variant-selection: yes
GO-controller-feasibility: yes, but conditional
FULL-SYSTEM-GO: not yet
```

Main risks identified by pro4:

```text
1. Acceptance is not yet a real llama.cpp trace.
2. Offline controller is not online controller.
3. d=15 should be downgraded until native T=16 exists.
4. End-to-end integration evidence is missing.
5. Strong baselines must include goodput-only adaptive and oracle replay.
```

Task direction:

```text
Create 06-17-real-online-controller-validation.
Use real llama.cpp trace or a controlled self-speculative path.
Implement or replay a lightweight EWMA controller.
Compare against fixed-d, goodput-only, and oracle baselines.
```
