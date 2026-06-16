# pro7 Guidance Summary

`doc/pro7.md` narrows the next decisive question:

```text
Can a selected-only two-action controller beat fixed d=3 under
position-complete, commit-aware replay?
```

The required order is:

```text
1. Verify prefix-state equivalence.
2. Generate a position-complete candidate trace.
3. Replay policies with true commit semantics:
   next_position = position + 1 + accepted_count(selected_d)
4. Start with arms d in {0,3}.
5. Only add d=1/d=7 after {0,3} passes.
```

This round must not return to aggregate sweeps or kernel tuning. The kernel
evidence is already strong; the active risk is controller evidence quality.

Decision labels:

```text
GO:
  selected-only policy beats fixed d=3 by >= 8% and reaches >= 90% oracle.

CONDITIONAL:
  selected-only policy beats fixed d=3 but reaches only 85-90% oracle.

NO-GO:
  fixed d=3 is within 3% of every selected-only policy.
```
