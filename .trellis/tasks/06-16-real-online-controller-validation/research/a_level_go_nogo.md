# A-Level Go/No-Go

Date: 2026-06-17 Asia/Shanghai

## Bottom Line

```text
A-level candidate found? NO
```

This is not a No-Go for every possible future RVV verifier project. It is a
No-Go for claiming an A-level VeriCurve-RV mechanism from the current evidence.

The prior Version B framing should remain only a fallback boundary, not a paper
commitment. The current evidence is not enough to justify writing yet.

## A-Level Gates

A candidate must pass all five gates:

1. It changes framework decisions in a way not explained by kernel speed alone.
2. It beats or clearly explains goodput-only / fixed-d baselines.
3. It generalizes beyond one hand-picked workload or setting.
4. It has a falsifiable abstraction or interface, not only an implementation trick.
5. It is RISC-V-first but not simply a GPU idea ported to RISC-V.

## Candidate Results

| candidate | status | reason |
|---|---|---|
| Verification-plan synthesis | FAIL_CURRENT_EVIDENCE | Two-T4 composed T8 gives `C8/C1=2.798736`; multi-point gain remains `0.000194%`; selected policy beats goodput by only `0.909599%`; rows2048 fails robustness. |
| Policy-regime phase model | PROMISING_EXPLANATION_NOT_A_LEVEL | It explains why current policy collapses to `{d0,d3}` and predicts `C8/C1 <= 2.1` is needed for d7, but it does not itself beat baselines. |
| Working-set-aware RVV curve family | FAIL_CURRENT_EVIDENCE | rows128 and rows512 pass, but rows2048 shaped `C4/C1=2.839325`, above the strict broad-claim gate. |
| Selected-only controller | FAIL_CURRENT_EVIDENCE | It is near-go against fixed d3 but goodput-only nearly ties and oracle reach remains below 90%. |
| Verifier-curve ABI/profile interface | NOT INDEPENDENTLY PASSED | Useful only if verification-plan synthesis or working-set-aware curve family gains evidence. |

## Why Current VeriCurve-RV Collapses

### 1. Kernel paper risk

The strongest measured artifact is still:

```text
R8T4 / RTile x TTile changes C_verify(4)
```

That is real and valuable, but by itself it can be read as row-blocked low-bit
GEMM beating repeated GEMV. The regime-shift table prevents it from being a
pure microbenchmark, but it does not yet create a broad mechanism.

### 2. Two-action policy collapse

Current best curve:

```text
C4/C1 = 1.399368
C8/C1 = 3.454508
```

The good C4 opens d3, but the poor C8 kills d7. The oracle over
`{d0,d1,d3,d7}` chooses only:

```text
d0=1148; d3=408
```

Adding d1/d7 gives:

```text
multi_vs_two_oracle_gain = 0.0%
```

### 3. Goodput equivalence

Selected-only curve-aware:

```text
9.078115 ms/token
```

Best selected-only goodput:

```text
9.160689 ms/token
```

Difference:

```text
0.909599%
```

This is far below the `>=5%` gate for a controller contribution.

### 4. Robustness is not broad

Measured shaped curves:

```text
rows128 C4/C1 = 1.701057
rows512 C4/C1 = 1.399368
rows2048 C4/C1 = 2.839325
```

The rows2048 degradation blocks a broad model/working-set claim.

## What Would Change the Answer

The only credible path back to an A-level mechanism is:

```text
native or synthesized RVV T8 verifier plan with C8/C1 <= 2.1,
plus robustness that does not collapse at rows2048 or an alternate realistic
setting.
```

Why this matters:

- Threshold sweep shows multi-point oracle gain stays above 5% only when T8 is
  around `<=2.1 x T1`.
- Current native T8 is `3.454508 x T1`.
- Two T4 tiles are `2.798736 x T1`, still too slow.

If a real T8 plan reaches this threshold and goodput-only no longer ties, then
C1 verification-plan synthesis becomes a plausible A-level direction.

## Recommended Pivot

Recommended pivot:

```text
Pivot from "VeriCurve-RV as current controller/system" to a sharper falsifiable
project:

RVV verifier-plan synthesis for speculative decoding, with T8 as the decisive
gate.
```

Do not write the paper yet. Do not optimize R8T4 further. The next build task,
if continuing, should be:

```text
Build and measure a real native/composed T8 verifier plan that targets
C8/C1 <= 2.1 on rows512, then repeat the same plan on rows2048 or an alternate
quant/path.
```

Stop condition:

```text
If T8 cannot reach C8/C1 <= 2.1, or if it reaches the threshold but goodput-only
still matches the plan-aware policy, No-Go the VeriCurve-RV A-level system idea.
```

If that stop condition fires, the remaining publishable material is a scoped
kernel/measurement result, not an A-level system mechanism.
