# PRD: Real Online Controller Validation

## Goal

Turn the current offline/proxy controller result into real llama.cpp trace and
online-controller evidence.

The prior task established that the curve-aware controller is promising but not
yet a full-system result. This task determines whether real llama.cpp acceptance
behavior and an online EWMA decision policy can promote the controller from
`CONDITIONAL PAPER GO` to `FULL SYSTEM GO`.

Current critique-resolution update:

```text
Conservative fallback boundary: B. Curve-shaping systems paper
Curve-shaping beyond kernel speedup: GO
Two-action vs multi-point controller: TWO-ACTION
Selected-only controller: CONDITIONAL
Goodput-only comparison: TIE
Robustness: SCOPED
```

The paper should not currently be framed as a strong controller-algorithm
paper. It should also not be written yet as Version B. The safe mainline is a
fallback boundary only: verifier cost-curve shaping plus policy-regime shift,
with a simple selected-only `{d=0,d=3}` curve-gated policy as conditional
support.

Current A-level innovation update:

```text
A-level candidate found? NO
closest candidate: verifier-plan synthesis
decisive next gate: native/composed RVV T8 with C8/C1 <= 2.1
current C8/C1: 3.454508
two-T4 composed C8/C1: 2.798736
```

Do not optimize only R8T4, write Version B, or claim an adaptive-controller
paper unless the T8 verifier-plan synthesis gate changes the action set and
beats fixed/goodput killer baselines.

## Inherited State

Previous status:

```text
Curve-shaping kernel: STRONG GO
  C_best(4) / C_best(1) = 1.399
  speedup_vs_old_T4 = 2.858x

Schedule crossover: GO
  T=1/2 old vecdot wins
  T>=4 row-blocked RTile x TTile wins

Controller offline/proxy: CONDITIONAL PAPER GO
  no speculation = 12.024 ms/token
  best fixed mixed = 9.048 ms/token
  VeriCurve offline = 8.226 ms/token
  oracle = 7.190 ms/token
  VeriCurve beats fixed mixed by about 10.0%
  VeriCurve reaches 87.4% oracle
```

Main risk:

```text
The previous acceptance signal was deterministic ngram proxy data, not a real
llama.cpp speculative loop trace.
```

## Requirements

### R1: Real llama.cpp Acceptance Trace

Use a real llama.cpp speculative or prompt-lookup path first. Prefer
`examples/lookup` because it uses ngram/prompt lookup and does not require a
separate draft model.

Required fields for the target trace format:

```text
prompt_id
workload_type
step_id
draft_source
requested_d
draft_tokens
target_tokens
accepted_count
acceptance_prefix_length
selected_T
selected_verifier_variant
verify_latency_ms
draft_latency_ms
total_latency_ms
```

MVP acceptance trace may start with aggregate llama.cpp lookup output if a
source patch cannot be applied safely in the first pass. Any aggregate-only
result must be labeled as such.

### R2: Integrated C_draft(d) and C_verify(T)

For `d in {1,3,7}`:

```text
T = 1 + d
record C_draft_real(d)
record C_verify_real(T) or target decode proxy timing
record selected verifier variant
record total emitted-token latency
```

Confirm whether the existing `GGML_VERICURVE_TRACE` instrumentation reports the
expected low-bit route:

```text
T=1/2: old vecdot if still best
T>=4: R8T4/R8 no-pack or the integrated path's actual selected route
```

### R3: Online EWMA Controller

Implement or simulate a minimal controller:

```text
candidates: d in {0,1,3,7}
EWMA alpha: 0.2 or 0.3
window: 8 or 16 emitted tokens
switch margin: 5%
minimum dwell: 2 windows
objective: J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

The first implementation may be a replay controller over real traces before a
llama.cpp runtime patch.

### R3b: Candidate-Aligned Replay

Aggregate d sweeps are insufficient for controller replay. The task must collect
candidate-aligned rows from the same pseudo/runtime position:

```text
d in {0,1,3,7}
same chunk_id
same step_id
same pseudo_position
same pseudo state before commit
```

Required output:

```text
results/aligned_candidate_trace.csv
results/aligned_replay_summary.csv
results/aligned_replay_by_workload.csv
results/online_ewma_replay_trace.csv
patches/aligned_candidate_trace.patch
research/aligned_candidate_trace.md
research/aligned_replay_summary.md
```

### R4: Strong Baselines

Compare:

```text
B0 no speculation
B1 fixed d=1
B2 fixed d=3
B3 fixed d=7
B4 offline-best fixed d over mixed workload
B5 offline-best fixed d per workload
B6 goodput-only adaptive
B7 VeriCurve online EWMA
B8 oracle replay
```

Metrics:

```text
ms / emitted token
tokens / second
regression on low-acceptance workload
controller overhead
oracle reach
switch count
```

## Go/No-Go Criteria

```text
FULL SYSTEM GO:
  VeriCurve online beats offline-best fixed mixed by >= 8%
  and reaches >= 90% oracle
  and does not regress no-spec on low-acceptance workloads by > 3%
  and controller overhead < 1%.

STRONG PAPER GO:
  VeriCurve online beats goodput-only adaptive by >= 5%
  and reaches >= 90% oracle.

CONDITIONAL PAPER GO:
  VeriCurve beats default/fixed but not offline-best or not 90% oracle.

NO-GO controller:
  offline-best fixed d or goodput-only adaptive is within 3-5% of VeriCurve.
```

## Artifacts

Required:

```text
research/pro4_guidance_summary.md
research/rvv_safety_check.md
research/remote_llamacpp_tree_audit.md
patches/llamacpp_acceptance_trace.patch
results/real_acceptance_trace.csv
research/real_acceptance_trace.md
results/integrated_cost_trace.csv
research/integrated_cost_trace.md
patches/online_ewma_controller.patch
results/online_controller_trace.csv
research/online_controller.md
results/controller_e2e_summary.csv
research/controller_e2e_summary.md
patches/aligned_candidate_trace.patch
results/aligned_candidate_trace.csv
results/aligned_replay_summary.csv
results/aligned_replay_by_workload.csv
results/online_ewma_replay_trace.csv
research/aligned_candidate_trace.md
research/aligned_replay_summary.md
research/workload_hardening.md
research/pro6_guidance_summary.md
scripts/replay_policy_family.py
results/replay_sanity_checks.csv
research/replay_correctness_audit.md
results/oracle_gap_breakdown.csv
research/oracle_gap_breakdown.md
results/policy_family_replay.csv
research/policy_family_replay.md
results/policy_train_test.csv
research/policy_train_test.md
research/pro7_guidance_summary.md
patches/pseudo_state_hash.patch
scripts/make_pseudo_state_hash_patch.py
results/prefix_state_equivalence.csv
research/prefix_state_equivalence.md
patches/position_complete_trace.patch
scripts/make_position_complete_trace_patch.py
results/position_complete_candidate_trace.csv
results/position_complete_trace_quality.csv
research/position_complete_candidate_trace.md
scripts/replay_commit_aware.py
results/commit_aware_replay_summary.csv
results/commit_aware_replay_by_workload.csv
results/commit_aware_selected_threshold_trace.csv
research/commit_aware_replay.md
research/two_action_policy_replay.md
results/commit_aware_train_test.csv
research/commit_aware_train_test.md
doc/VeriCurve-RV-Claude-Critique-Resolution-GoNoGo.md
scripts/resolve_claude_critique.py
results/regime_shift_table.csv
research/regime_shift_analysis.md
results/d_action_value.csv
research/two_action_or_multipoint.md
results/selected_only_policy_summary.csv
results/selected_only_policy_trace.csv
research/selected_only_policy.md
results/goodput_baseline_comparison.csv
research/goodput_baseline_comparison.md
results/curve_robustness_matrix.csv
research/curve_robustness.md
results/final_decision_matrix.csv
research/claude_critique_resolution_final.md
results/remote_claude_critique/rtile_ttile_rows128_r3.csv
results/remote_claude_critique/rtile_ttile_rows2048_r3.csv
scripts/search_a_level_mechanisms.py
results/innovation_curve_family_replay.csv
results/innovation_t8_threshold_sweep.csv
results/innovation_decision_matrix.csv
research/innovation_search.md
research/a_level_go_nogo.md
```

If a full artifact cannot be produced safely in this task, create the best
available precursor and label it explicitly as `aggregate-only`,
`patch-only`, or `blocked-by-model/build`.

## Out of Scope

- Do not optimize the R8T4 kernel further in this task.
- Do not promote `d=15` into the mainline unless a native T=16 verifier is
  measured.
- Do not run high-parallel builds or broad model sweeps on `rvv`.
- Do not mutate unrelated TianchenRV or control/canary llama.cpp trees.

## Technical Notes

- Remote work must stay under `~/vericurve-rv-lab/`.
- Reuse existing `~/vericurve-rv-lab/llama.cpp` only with recorded dirty-state
  and backend flags.
- Existing remote tree already has `GGML_VERICURVE_TRACE` low-bit route
  instrumentation in `quants.c` and `repack.cpp`.
- Available full model candidates include `/home/ubuntu/llama-2-7b-chat.Q4_0.gguf`;
  `llama.cpp/models` itself currently contains vocab/test GGUF files only.
