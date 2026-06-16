# VeriCurve-RV: Claude Critique Response and Final Validation Task Plan

## 0. Current Decision State

Current status:

```text
VeriCurve-RV mainline: CONTINUE
Curve-shaping verifier kernel: STRONG GO
Position-complete replay: GO
Selected-only controller: CONDITIONAL / NEAR-GO
FULL SYSTEM GO: NOT YET
```

The strongest current evidence is:

```text
Old llama.cpp/RVV verifier:
  C_old_T4 = 48.085 ms

Best T1 baseline:
  C_best_T1 = 12.024 ms

Row-blocked R8T4 verifier:
  C_candidate_T4_total = 16.826 ms
  speedup_vs_old_T4 = 2.858x
  curve_ratio = C_candidate_T4_total / C_best_T1 = 1.399

Variant crossover:
  T=1/2: old vec-dot wins
  T=4/8: row-blocked R8 path wins
```

The direct R1T4 attempt failed, so the viable direction is **not** “make token-width visible.” The viable direction is:

```text
RTile × TTile verifier microkernel
  -> reshapes C_verify(T)
  -> changes speculation break-even
  -> enables runtime policy over d={0,3} or d={0,1,3,7}
```

The next work should not broaden the idea. It should answer Claude’s remaining reviewer-level objections with targeted experiments.

---

## 1. Final Working Thesis

Use this thesis for now:

> VeriCurve-RV studies RISC-V/RVV low-bit speculative verification as a **cost-curve shaping problem**. The default llama.cpp/RVV path makes `C_verify(T)` nearly linear because T token positions are effectively handled as repeated single-RHS vec-dots. A naive direct R1T4 extension fails. A layout-aware RTile×TTile verifier reshapes `C_verify(T)`, making speculation economically viable. The remaining systems question is whether this reshaped verifier curve supports a runtime policy that meaningfully outperforms fixed speculation and goodput-only adaptation.

Avoid these claims:

```text
Do not claim: generic kernel-centric scheduler is new.
Do not claim: adaptive speculation is new.
Do not claim: shape-conditioned kernel dispatch is new.
Do not claim: multi-row GEMM itself is new.
```

The paper must claim something narrower:

```text
We identify and reshape the verifier cost curve needed by speculative inference on RVV.
Then we test whether that reshaped curve changes speculation policy.
```

---

## 2. Claude Critique Checklist

Claude raised five sharp objections. The next agent task must explicitly handle them.

### Critique A: “Is curve shaping just a row-blocked GEMM kernel?”

Risk:

```text
Reviewer says:
  R8T4 is just a row-blocked low-bit GEMM microkernel.
  GEMM beating repeated GEMV is old news.
```

Required response:

Show that the contribution is not “R8T4 is fast,” but:

```text
1. Current llama.cpp/RVV verifier curve is linear.
2. Direct R1T4 fails, proving token-width visibility alone is insufficient.
3. RTile×TTile, not T-only, is the required verifier execution unit.
4. The reshaped curve changes the speculation break-even point.
5. Policy decisions differ under old curve vs new curve.
```

Agent must produce a **regime-shift table**:

```text
workload | old_curve_best_d | new_curve_best_d | policy implication
chat     | ?                | ?                | ?
code     | ?                | ?                | ?
rag      | ?                | ?                | ?
structured | ?              | ?                | ?
```

Go condition:

```text
GO if at least one high-acceptance workload changes from d=0/1 under old curve to d=3 under new curve,
and at least one low-acceptance workload remains d=0/1 under new curve.
```

No-Go condition:

```text
NO-GO if the new curve only produces a uniform fixed d=3 policy with no meaningful policy distinction.
```

---

### Critique B: “Your curve is actually a binary T=1 vs T=4 switch.”

Risk:

```text
Reviewer says:
  This is not curve-aware control.
  It is just speculation on/off with a threshold.
```

Required response:

Do not pretend there is a smooth continuous curve if the data only supports two useful actions. There are two acceptable outcomes:

#### Outcome B1: Multi-point curve exists

If T=1/2/4/8 have meaningful different optimal choices, keep the “curve-aware” story.

Agent must test:

```text
C_verify_best(T) for T={1,2,4,8,16}
winner_variant(T)
policy value of d={0,1,3,7}
```

Go condition:

```text
GO if d=1 or d=7 is optimal for some workload or hardware/quant setting,
or if T=8 has a distinct verifier variant and distinct policy role.
```

#### Outcome B2: Only {0,3} matters

If only d={0,3} matters, be honest:

```text
This paper is not about continuous curve optimization.
It is about turning speculation from always-off / always-on into a verifier-curve-gated two-action policy.
```

Then rename the controller mechanism internally as:

```text
curve-gated speculation
```

not:

```text
continuous curve optimization
```

Go condition for B2:

```text
GO if selected-only {0,3} policy beats fixed d=3 by >=8% and low-acceptance regression <=3%.
```

---

### Critique C: “Replay is not runtime.”

Risk:

```text
Reviewer says:
  Commit-aware replay still overestimates controller performance.
  Runtime observes only selected_d, not all candidate outcomes.
```

Required response:

The final Go/No-Go must include a real runtime `choose_d()` or a strictly selected-only replay with no full-information leakage.

Current position-complete replay is valuable, but not sufficient for full-system claim.

Agent must implement one of:

```text
Option 1: runtime choose_d loop in llama.cpp lookup-stats / lookup path
Option 2: selected-only replay where policy only observes chosen arm outcomes and probe outcomes
```

The selected-only policy should start with:

```text
actions: {d=0, d=3}
threshold: around 0.4
probe interval: 16
min d3 samples: 4
fallback: d=0
switch margin: 5%
```

Required metrics:

```text
ms/token
selected_d distribution
probe overhead
low-acceptance regression
oracle reach
comparison to fixed d=3
comparison to goodput-only adaptive
```

Full-system Go condition:

```text
runtime or selected-only controller beats fixed d=3 by >=8%
AND reaches >=90% oracle
AND low-acceptance regression <=3%
AND overhead <1%.
```

Conditional paper condition:

```text
beats fixed d=3 by 5-8% OR reaches 85-90% oracle.
```

No-Go condition:

```text
fixed d=3 remains within 3-5% of selected-only policy.
```

---

### Critique D: “Missing TurboSpec-style baseline on shaped verifier.”

Risk:

```text
Reviewer says:
  A pure goodput-feedback controller over the R8T4 verifier may match your curve-aware controller.
  Then your curve model is unnecessary.
```

Required response:

Agent must implement or replay a **goodput-only adaptive baseline using the same shaped verifier curve**.

This baseline must not use `C_verify(T)` directly. It observes only realized throughput / emitted tokens per cost.

Suggested baseline:

```text
arms: {0,3} first; optional {0,1,3,7}
reward: emitted_tokens / observed_cost
policy: epsilon-greedy or UCB
probe interval / exploration budget matched to VeriCurve policy
```

Required comparison:

```text
VeriCurve selected-only controller
vs
Goodput-only adaptive controller over same R8T4 verifier
vs
Fixed d=3
vs
Oracle
```

Go condition:

```text
GO if VeriCurve beats goodput-only by >=5% or reaches oracle faster with less exploration/regression.
```

Conditional:

```text
If VeriCurve ≈ goodput-only, controller novelty weakens.
Then paper should emphasize curve-shaping verifier and policy analysis, not controller algorithm.
```

---

### Critique E: “Does the curve survive model size / quant / working-set changes?”

Risk:

```text
Reviewer says:
  The R8T4 curve_ratio=1.399 may hold only for one synthetic layer or small working set.
  On real 7B layers, the advantage may shrink.
```

Required response:

Agent must validate curve shaping across at least two of the following axes:

```text
model/layer size: synthetic rows, 1B-like, 3B-like, 7B-like if available
quant: Q4_0, Q4_K_M, Q8 if feasible
working-set size: rows/hidden sweep
integrated path: lookup / llama.cpp real run smoke
```

Minimum required table:

```text
case | C_best_T1 | C_best_T4 | ratio_T4_T1 | winner_T1 | winner_T4 | conclusion
```

Go condition:

```text
GO if at least one realistic model/quant case keeps C_best(4)/C_best(1) <= 1.8,
and no core claim relies solely on a tiny synthetic case.
```

Conditional:

```text
If only small working sets work, restrict paper scope honestly to models/quant/settings where curve shaping is effective.
```

No-Go for broad claim:

```text
If realistic 7B/Q4 verifier ratio degrades above 2.5-3.0, do not claim general LLM speedup.
Reframe as microkernel feasibility / small-model edge setting.
```

---

## 3. Final Agent Task: “Claude Critique Resolution Go/No-Go”

Create or continue a Trellis task named:

```text
06-XX-claude-critique-resolution-gonogo
```

Goal:

```text
Resolve the remaining reviewer risks in VeriCurve-RV:
1. Is this more than a fast R8T4 kernel?
2. Is the controller more than a trivial d=0/d=3 threshold switch?
3. Does curve-aware control beat goodput-only adaptive control?
4. Does curve shaping hold across realistic model/quant/working-set settings?
5. Should the final paper be strong-system version A or curve-shaping version B?
```

---

## 4. Task Breakdown

### Task 1: Regime-Shift Analysis

Inputs:

```text
C_old(T)
C_new_best(T)
C_draft(d)
position-complete candidate trace
commit-aware replay script
```

Outputs:

```text
results/regime_shift_table.csv
research/regime_shift_analysis.md
```

Required rows:

```text
workload
old_curve_best_d
new_curve_best_d
fixed_d3_cost_old
fixed_d3_cost_new
no_spec_cost
policy_interpretation
```

Gate:

```text
GO if old curve and new curve imply different best_d for high-acceptance workloads,
and low-acceptance workloads still prefer d=0/1.
```

---

### Task 2: Multi-Point Curve or Two-Action Honesty

Evaluate whether d={1,7} matter.

Outputs:

```text
results/d_action_value.csv
research/two_action_or_multipoint.md
```

Required analysis:

```text
best policy over {0,3}
best policy over {0,1,3,7}
additional gain from adding d=1/7
whether d=7 failure is due to C_verify(8), low acceptance, or replay policy
```

Gate:

```text
If {0,1,3,7} improves over {0,3} by >=5%, keep multi-point curve framing.
If improvement <3%, use honest two-action curve-gated framing.
```

---

### Task 3: Selected-Only Runtime or Replay

Implement selected-only evaluation.

Preferred order:

```text
1. selected-only commit-aware replay
2. runtime choose_d if selected-only replay passes
```

Policies:

```text
fixed d=0
fixed d=3
threshold {0,3}
periodic probe {0,3}
goodput-only adaptive {0,3}
VeriCurve curve-aware {0,3}
oracle
```

Outputs:

```text
results/selected_only_policy_summary.csv
results/selected_only_policy_trace.csv
research/selected_only_policy.md
```

Gate:

```text
FULL SYSTEM GO if:
  VeriCurve beats fixed d=3 by >=8%
  and reaches >=90% oracle
  and beats goodput-only by >=5%
  and low-acceptance regression <=3%.

CONDITIONAL if:
  VeriCurve beats fixed d=3 by 5-8%
  or reaches 85-90% oracle.

NO-GO controller if:
  fixed d=3 or goodput-only is within 3-5%.
```

---

### Task 4: Goodput-Only Baseline on Shaped Curve

This is mandatory.

Outputs:

```text
results/goodput_baseline_comparison.csv
research/goodput_baseline_comparison.md
```

Goodput baseline rules:

```text
Do not use C_verify table directly.
Use observed reward = emitted_tokens / observed_cost.
Same action set and probe budget as VeriCurve policy.
```

Gate:

```text
GO if curve-aware policy clearly beats or learns faster than goodput-only.
CONDITIONAL if comparable.
NO-GO for controller novelty if goodput-only matches or beats curve-aware.
```

---

### Task 5: Model / Quant / Working-Set Robustness

Outputs:

```text
results/curve_robustness_matrix.csv
research/curve_robustness.md
```

Minimum matrix:

```text
case
rows
hidden/n
quant
C_best_T1
C_best_T4
ratio_T4_T1
winner_T1
winner_T4
speedup_vs_old_T4
```

Include at least:

```text
current synthetic case
larger rows / working set
one real 7B-layer-like case if available
one alternate quant path if feasible
```

Gate:

```text
GO if C_best(4)/C_best(1) <= 1.8 in at least one realistic setting,
and paper scope is adjusted to match where it holds.

CONDITIONAL if only synthetic/small cases work.

NO-GO for broad paper claim if realistic cases lose curve shaping.
```

---

## 5. Final Decision Matrix

After Tasks 1-5, agent must output exactly this table.

```text
Final Decision Matrix

A. Curve-shaping beyond kernel speedup:
  status: GO / CONDITIONAL / NO-GO
  evidence:
  interpretation:

B. Two-action vs multi-point controller:
  status: MULTI-POINT / TWO-ACTION / NO-GO
  evidence:
  interpretation:

C. Selected-only controller:
  status: FULL GO / CONDITIONAL / NO-GO
  evidence:
  interpretation:

D. Goodput-only comparison:
  status: CURVE-AWARE WINS / TIE / GOODPUT WINS
  evidence:
  interpretation:

E. Robustness across model/quant/working-set:
  status: BROAD / SCOPED / WEAK
  evidence:
  interpretation:

Final paper version:
  A. Strong system paper:
     Curve-shaped verifier + selected-only adaptive controller
  B. Curve-shaping systems paper:
     RTile×TTile verifier reshapes C_verify(T), simple policy implication
  C. Kernel/measurement fallback:
     Not enough systems contribution

Recommended next action:
```

---

## 6. How to Decide Final Paper Version

### Version A: Strong System Paper

Use if:

```text
selected-only controller FULL GO
curve-aware beats goodput-only
realistic robustness at least SCOPED
```

Title:

```text
VeriCurve-RV: Curve-Shaped Verification and Adaptive Speculation for RISC-V LLM Inference
```

Main contributions:

```text
1. RVV verifier curve characterization
2. RTile×TTile curve-shaping verifier
3. selected-only curve-aware controller
4. end-to-end speculative inference speedup
```

### Version B: Curve-Shaping Systems Paper

Use if:

```text
controller is CONDITIONAL
or goodput-only ties
or fixed d=3 remains strong
but curve-shaping is robust and regime shift is clear
```

Title:

```text
VeriCurve-RV: Curve-Shaped Verification for RISC-V Speculative Inference
```

Main contributions:

```text
1. default llama.cpp/RVV verifier curve is linear
2. direct R1T4 negative result
3. RTile×TTile verifier reshapes C_verify(T)
4. shaped curve changes which speculation policies are viable
5. simple d=0/d=3 policy analysis
```

Important: Version B is not a kernel paper only if it contains Contribution 4.

### Version C: Kernel / Measurement Fallback

Use if:

```text
curve-shaping does not hold beyond narrow synthetic case
or policy implication disappears
```

Then do not oversell framework contribution.

---

## 7. One-Sentence Reminder for the Agent

> The next task is not to make R8T4 faster. The next task is to prove whether R8T4’s reshaped verifier curve creates a systems-level policy advantage that cannot be explained by “a faster kernel” or by “ordinary goodput feedback.”

