# pro6 Guidance Summary

`doc/pro6.md` changes the next question from "does aligned replay look good" to:

```text
Is the aligned replay commit-aware enough to support selected-only online
controller claims?
```

The required progression is:

```text
1. audit replay semantics
2. decompose the full-info EWMA to oracle gap
3. test simple offline and selected-only policy families
4. use a train/test split before reporting tuned policy results
```

The main warning is that an aligned trace from one committed trajectory is not
automatically a valid selected-path trace. A realistic replay must advance:

```text
next pseudo_position = current pseudo_position + 1 + accepted_count(selected_d)
```

If that next position is not present in the trace, the replay cannot continue
exactly for that selected policy. In that case, low cost numbers from a
row-by-row scan are diagnostic only, not online-controller evidence.

Go/No-Go interpretation for this round:

```text
GO:
  replay is commit-aware and selected-only policies beat fixed d=3.

CONDITIONAL:
  scan-mode policies look promising but exact selected-only replay needs a
  position-complete trace or a runtime choose_d run.

NO-GO:
  fixed d=3 is within 3% of every realistic selected-only policy.
```

This round should not do more kernel tuning. The kernel curve remains strong;
the active risk is the controller evidence path.
