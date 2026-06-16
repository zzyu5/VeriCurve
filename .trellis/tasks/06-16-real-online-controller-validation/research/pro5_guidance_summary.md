# pro5 Guidance Summary

`doc/pro5.md` reframes the next decisive question:

```text
The controller question cannot be answered from aggregate d=1/3/7 sweeps or
d=3-only per-step traces.
```

Required next step:

```text
Collect candidate-aligned evidence from the same pseudo/runtime position:
  d in {0,1,3,7}
  same pseudo_state_before
  accepted_count for each candidate
```

Reason:

```text
Separate d sweeps can follow different pseudo-output trajectories. They are
useful for aggregate J estimates, but cannot replay oracle, EWMA, or switching
controllers.
```

Primary task direction:

```text
candidate-aligned-controller-replay
```

Decision target:

```text
If VeriCurve replay beats fixed d=3 by >=8% and reaches >=90% oracle, continue
toward a full online controller.

If fixed d=3 remains close to oracle, demote the adaptive controller and focus
the paper on RTile x TTile verifier curve shaping plus a simple fixed-d policy.
```

The task should not return to kernel tuning unless the integrated path loses the
R8T4 curve.
