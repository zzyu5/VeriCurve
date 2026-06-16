# A-Level Innovation Search

Date: 2026-06-17 Asia/Shanghai

This note intentionally does **not** lock VeriCurve-RV into Version B. It treats
the prior "curve-shaping systems paper" as a conservative fallback boundary and
searches for a larger mechanism-level contribution.

## Inputs

Local evidence:

- `results/final_decision_matrix.csv`
- `results/regime_shift_table.csv`
- `results/d_action_value.csv`
- `results/selected_only_policy_summary.csv`
- `results/goodput_baseline_comparison.csv`
- `results/curve_robustness_matrix.csv`
- `results/remote_claude_critique/rtile_ttile_rows128_r3.csv`
- `results/remote_claude_critique/rtile_ttile_rows2048_r3.csv`

New discriminating script:

```text
scripts/search_a_level_mechanisms.py
```

Command:

```bash
python3 .trellis/tasks/06-16-real-online-controller-validation/scripts/search_a_level_mechanisms.py \
  --position-complete .trellis/tasks/06-16-real-online-controller-validation/results/position_complete_candidate_trace.csv \
  --verify .trellis/tasks/06-16-curve-aware-controller-feasibility/results/C_verify_best_curve.csv \
  --variant-timing .trellis/tasks/06-16-post-direct-t4-go-nogo/results/variant_timing.csv \
  --remote-rtile-results .trellis/tasks/06-16-real-online-controller-validation/results/remote_claude_critique \
  --out .trellis/tasks/06-16-real-online-controller-validation/results
```

Outputs:

- `results/innovation_curve_family_replay.csv`
- `results/innovation_t8_threshold_sweep.csv`
- `results/innovation_decision_matrix.csv`

## External Threat Surface

The following existing work threatens generic claims:

- [TurboSpec / goodput-guided speculative decoding](https://arxiv.org/abs/2406.14066) already frames speculation length as a runtime goodput optimization problem.
- [TurboSpec dissertation context](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/EECS-2025-224.html) strengthens the threat by combining offline profiling and online feedback for speculation control.
- [Sequoia](https://arxiv.org/abs/2402.12374) already performs hardware-aware speculative tree optimization using dynamic programming.
- [SpecInfer](https://arxiv.org/abs/2305.09781) already treats the target model as a tree verifier rather than an incremental decoder.
- [Medusa](https://arxiv.org/abs/2401.10774) and [EAGLE](https://arxiv.org/abs/2401.15077) already attack the draft/verification bottleneck with multi-head or feature-level speculation.
- [Ansor](https://arxiv.org/abs/2006.06762) threatens generic "kernel search / tensor program synthesis" claims.

Therefore, VeriCurve-RV cannot claim novelty by saying:

```text
adaptive speculation
goodput control
hardware-aware tree/speculation optimization
generic kernel autotuning
```

The only plausible A-level opening is narrower:

```text
RISC-V/RVV low-bit verification exposes a measurable verifier-curve family,
and speculation policy should be chosen from achievable verification plans,
not just from a scalar latency table or a single d.
```

## Candidate Mechanisms

### C1: Verification-Plan Synthesis

Core mechanism:

```text
Expose verifier plans P = {old vecdot, RTile x TTile variants, packing/layout
choices, composed T plans}, synthesize C_verify(T | P), then choose a
verification plan family jointly with speculation budget.
```

Why not just a faster kernel:

- It is not a single R8T4 point; it asks whether the runtime/compiler can expose
  a curve family and use different plans at T=1, T=4, T=8.
- The key A-level test is whether a plan family makes new policy regimes
  possible, especially d7/multi-point behavior.

Why not TurboSpec/goodput:

- TurboSpec-style control chooses speculation parameters from observed goodput.
- This candidate changes the action space before goodput sees it: the available
  verification plans determine whether goodput has a useful d7 option at all.

Existing work that threatens it:

- Sequoia hardware-aware tree optimizer.
- SpecInfer tree verification.
- Ansor/TensorIR-style tensor program search.

Falsifying experiment:

```text
If measured or composable verification plans do not make multi-point actions
valuable, or if goodput-only still matches curve-aware use of the plan family,
then the mechanism is not A-level.
```

Discriminating result:

```text
synth_split_T8_from_T4_rows512:
  C8/C1 = 2.798736
  multi_vs_two_oracle_gain = 0.000194%
  selected advantage vs goodput = 0.909599%
  rows2048 normalized C4/C1 = 2.839325
decision: FAIL_CURRENT_EVIDENCE
```

Important threshold finding:

```text
T8 must reach about C8/C1 <= 2.1 before multi-action oracle gain stays >= 5%.
Current best C8/C1 = 3.454508.
Two T4 tiles give C8/C1 = 2.798736, still not enough.
```

Interpretation:

This is the best A-level candidate, but it does not pass current evidence. It
does define a strong next falsification target: build or find a real RVV T8 plan
that reaches `C8/C1 <= 2.1`. Without that, the plan-family story remains a
diagnostic abstraction rather than a systems result.

### C2: Policy-Regime Phase Transition

Core mechanism:

```text
Derive a phase diagram mapping verifier curve ratios and workload acceptance to
policy regimes: no-spec d0, two-action {d0,d3}, fixed d3, or multi-point d7.
```

Why not just a faster kernel:

- It explains why the same kernel improvement changes code/rag/structured but
  not chat/chat_low.
- It explains why d7 fails: current T8 is too expensive.

Why not TurboSpec/goodput:

- Goodput observes outcomes; the phase model predicts which action set is even
  structurally viable from C(T) and acceptance.

Existing work that threatens it:

- TurboSpec-style work already models dynamic speculation length via goodput.
- Sequoia already optimizes speculation trees with hardware awareness.

Falsifying experiment:

```text
If a measured C8/C1 <= 2.1 still does not activate d7, or if goodput-only fully
explains all decisions without needing verifier-curve regimes, the phase model
is not distinctive.
```

Discriminating result:

```text
max C8/C1 with multi_vs_two_oracle_gain >= 5%: 2.1
current C8/C1: 3.454508
two-T4 composed C8/C1: 2.798736
current multi_vs_two_oracle_gain: 0.0%
```

Decision:

```text
PROMISING_EXPLANATION_NOT_A_LEVEL
```

This candidate explains current collapse into `{d0,d3}`, but explanation alone
does not beat killer baselines or generalize beyond the measured scope.

### C3: Working-Set-Aware RVV Curve Family

Core mechanism:

```text
RISC-V/RVV low-bit verifier curves depend on row working set and reuse pressure.
The plan interface should select different curve families for small/current vs
large rows.
```

Why not just a faster kernel:

- It makes curve shape depend on working-set regime, not only on a fixed kernel.

Why not TurboSpec/goodput:

- Goodput can react after performance changes; this mechanism would predict
  when a verifier plan is outside its valid regime.

Existing work that threatens it:

- General cache-aware blocking and tensor-program search.
- Ansor-like schedule search across CPUs/GPUs.

Falsifying experiment:

```text
If larger rows keep C4/C1 <= 1.8, the mechanism may pass; if larger rows degrade
above 2.5, broad A-level robustness fails.
```

Discriminating result:

```text
rows128 shaped C4/C1 = 1.701057
rows512 shaped C4/C1 = 1.399368
rows2048 shaped C4/C1 = 2.839325
decision: FAIL_CURRENT_EVIDENCE
```

The larger working set invalidates a broad robustness claim.

### C4: Selected-Only Curve-Aware Controller

Core mechanism:

```text
Use selected-only acceptance feedback plus C_verify(T) to choose d online.
```

Why not just a faster kernel:

- It is a runtime policy on top of shaped verifier curves.

Why not TurboSpec/goodput:

- It would need to use curve information to beat goodput-only feedback.

Existing work that threatens it:

- TurboSpec-style control directly targets goodput-based dynamic speculation.
- Online speculative decoding and similar controllers already adapt d.

Falsifying experiment:

```text
If goodput-only is within 3-5%, or oracle reach stays below 90%, controller
novelty fails.
```

Discriminating result:

```text
current selected curve-aware = 9.078115 ms/token
best goodput-only = 9.160689 ms/token
curve-aware advantage = 0.909599%
oracle reach = 0.891164
decision: FAIL_CURRENT_EVIDENCE
```

### C5: Verifier-Curve ABI / Profile Interface

Core mechanism:

```text
Create a runtime/compiler ABI where verifier kernels export an achievable curve
family: supported T values, layout constraints, row/working-set validity,
packing amortization, and expected C(T).
```

Why not just a faster kernel:

- It changes what a runtime sees from kernels: not "one latency", but a
  constrained curve family.

Why not TurboSpec/goodput:

- Goodput can choose among exposed actions, but the ABI defines the action space
  and invalid regimes.

Existing work that threatens it:

- TVM/Ansor/TensorIR expose/search tensor schedules.
- Sequoia exposes hardware-aware speculation tree choices.

Falsifying experiment:

```text
If exposing the curve-family ABI does not change any runtime decision compared
with a scalar best-latency table, or if all decisions reduce to fixed d3/goodput,
the ABI is only engineering structure.
```

Current status:

```text
Not passed. It is a useful implementation direction only if C1 or C3 gains
measured evidence.
```

## Killer Baseline Coverage

Covered in `results/innovation_curve_family_replay.csv`:

- R8T4 + fixed d3: `fixed_d3_ms`
- R8T4 + goodput-only controller: `goodput_ucb_ms`
- best fixed policy per workload: `best_fixed_per_workload_ms`
- workload-label upper bound: `workload_label_ms`
- old linear verifier curve: `old_linear_rows512`
- larger working set: `dynamic_plan_family_rows2048_*`

Key current rows512 baseline facts:

```text
current_best_rows512:
  fixed d3 = 10.248179 ms/token
  goodput UCB = 9.160689 ms/token
  selected curve-aware = 9.078115 ms/token
  best fixed per workload = 9.155243 ms/token
  multi_vs_two oracle gain = 0.0%
```

## A-Level Search Outcome

No candidate currently passes all A-level gates.

The closest candidate is C1, verification-plan synthesis, but current measured
or composable plans do not create a useful multi-point action set. The decisive
missing evidence is a real RVV T8 verifier plan with approximately:

```text
C8/C1 <= 2.1
```

Until such a plan exists and survives at least one robustness setting, the
project does not have an A-level mechanism-level result.
