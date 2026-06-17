# Real RVV T8 Gate

Date: 2026-06-17 Asia/Shanghai

## Bottom Line

```text
Did real RVV T8 reach the decisive gate? YES.
Best rows512 C8/C1 = 1.754.
Rows2048 robustness C8/C1 = 2.130.
```

This overturns the previous replay-only provisional No-Go. The earlier
statement "A-level candidate found? NO" is no longer the right live conclusion,
because it was made before measuring an optimized real RVV T8 verifier plan.

## Best Candidate

Rows512 best:

```text
candidate: native_T8_packed_rhs_rowblocked_weights
R: 16
C_best_T1: 12.051416 ms
C_old_T8: 96.195039 ms
C_candidate_T8: 21.144 ms
C8/C1: 1.754
speedup_vs_old_T8: 4.550x
max_abs: 0
max_rel: 0
gate: PASS_STRICT_T8
```

Rows2048 robustness best:

```text
candidate: native_T8_packed_rhs_rowblocked_weights
R: 16
C_best_T1: 42.917581 ms
C_old_T8: 316.249916 ms
C_candidate_T8: 91.410 ms
C8/C1: 2.130
speedup_vs_old_T8: 3.460x
max_abs: 0
max_rel: 0
gate: NEAR_PASS_T8
```

Rows2048 degrades relative to rows512, but it does not collapse back to the
old near-linear T8 regime. The degradation is a robustness warning, not a
fatal failure for the T8 gate.

## Why This Is Not Just The Old R8T4 Result

The prior R8T4 result was:

```text
C_candidate_T4_total = 16.826 ms
C4/C1 = 1.399
```

That result made `d=3` viable, but not `d=7`.

This task measured real T8 plans. The important contrast is:

```text
best real composed 2xT4 rows512:
  candidate: composed_2xT4_packed_rhs_rowblocked_weights, R=16
  C8/C1 = 2.432

best real native T8 rows512:
  candidate: native_T8_packed_rhs_rowblocked_weights, R=16
  C8/C1 = 1.754
```

The successful path is not "two T4 calls are enough". Native T8 with a
rowblocked verifier plan and packed RHS is materially better and crosses the
threshold that the replay sweep predicted.

## Gate Decision

Real RVV T8 verifier-plan gate:

```text
GO
```

Meaning:

```text
The mechanism-level candidate "RVV verifier-plan synthesis" is alive.
Real T8 can change the speculation action space beyond {d0,d3}.
```

Non-meaning:

```text
This is not permission to write the paper yet.
This is not proof of a selected-only online controller.
This is not a Version B fallback result.
```

Next mechanism task:

```text
Design and validate a low-overhead selected-only or limited-observability
multi-action plan-aware controller that can exploit d7 without using oracle
information.
```
