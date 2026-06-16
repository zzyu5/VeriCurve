#!/usr/bin/env python3
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import replay_commit_aware as base  # noqa: E402
import resolve_claude_critique as rc  # noqa: E402


DS = [0, 1, 3, 7]
TWO_ACTION = [0, 3]
MULTI_ACTION = [0, 1, 3, 7]


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def clone_verify(verify):
    return {t: {"ms": v["ms"], "winner": v["winner"]} for t, v in verify.items()}


def load_variant_curves(path):
    rows = read_csv(path)
    curves = defaultdict(dict)
    for row in rows:
        variant = row["variant"]
        t = int(row["T"])
        curves[variant][t] = {
            "ms": float(row["avg_ms"]),
            "winner": variant,
        }
    return curves


def complete_curve(curve, fallback):
    out = clone_verify(fallback)
    for t, value in curve.items():
        out[t] = {"ms": value["ms"], "winner": value["winner"]}
    return out


def dynamic_min_curve(curves, fallback, name):
    out = clone_verify(fallback)
    for t in [1, 2, 4, 8]:
        best = out[t]
        for variant, curve in curves.items():
            if t not in curve:
                continue
            if curve[t]["ms"] < best["ms"]:
                best = {"ms": curve[t]["ms"], "winner": variant}
        out[t] = {"ms": best["ms"], "winner": f"{name}:{best['winner']}"}
    return out


def old_curve_from_rtile_matrix(matrix_rows):
    old = {}
    for row in matrix_rows:
        t = int(row["T"])
        if t in old:
            continue
        old[t] = {
            "ms": float(row["avg_ms"]) / float(row["ratio_vs_old_T"]),
            "winner": "old_vecdot_nrc1",
        }
    return old


def dynamic_curve_from_rtile_csv(path):
    matrix, layout = rc.parse_rtile_sections(Path(path))
    old = old_curve_from_rtile_matrix(matrix)
    curve = complete_curve({}, old)
    for row in matrix:
        t = int(row["T"])
        candidate = {
            "ms": float(row["avg_ms"]),
            "winner": f"R{row['R']}_{row['layout']}",
        }
        if candidate["ms"] < curve[t]["ms"]:
            curve[t] = candidate
    for row in layout:
        t = int(row["T"])
        candidate = {
            "ms": float(row["C_total_ms"]),
            "winner": f"R{row['R']}_{row['layout']}",
        }
        if candidate["ms"] < curve[t]["ms"]:
            curve[t] = candidate
    return curve


def scale_curve_to_reference(curve, reference_t1_ms):
    # Replay acceptance is independent of absolute row count. For working-set
    # comparisons, normalize C1 so policy changes reflect curve shape, not a
    # different number of output rows.
    factor = reference_t1_ms / curve[1]["ms"]
    return {
        t: {"ms": v["ms"] * factor, "winner": f"normalized:{v['winner']}"}
        for t, v in curve.items()
    }


def build_curves(args):
    old512 = rc.load_verify(Path(args.verify), "old")
    best512 = rc.load_verify(Path(args.verify), "best")
    variants = load_variant_curves(Path(args.variant_timing))
    curves = {
        "old_linear_rows512": old512,
        "current_best_rows512": best512,
        "static_R8_no_pack_rows512": complete_curve(variants["R8_no_pack"], old512),
        "static_R4_no_pack_rows512": complete_curve(variants["R4_no_pack"], old512),
        "dynamic_plan_family_rows512": dynamic_min_curve(variants, old512, "rows512"),
    }

    split = clone_verify(best512)
    if 4 in split and 8 in split:
        split[8] = {
            "ms": min(split[8]["ms"], 2.0 * split[4]["ms"]),
            "winner": "synth_min(native_T8,two_T4_tiles)",
        }
    curves["synth_split_T8_from_T4_rows512"] = split

    remote_dir = Path(args.remote_rtile_results)
    for path in sorted(remote_dir.glob("rtile_ttile_rows*_r*.csv")):
        curve = dynamic_curve_from_rtile_csv(path)
        rows = next(iter(read_csv(path)))["rows"]
        curves[f"dynamic_plan_family_rows{rows}_absolute"] = curve
        curves[f"dynamic_plan_family_rows{rows}_normalized"] = scale_curve_to_reference(curve, best512[1]["ms"])

    return curves


def replay_curve(name, verify, position_complete):
    _combined, by_chunk = base.load_position_complete(position_complete, verify)
    two = rc.replay_oracle_actions(by_chunk, verify, TWO_ACTION)
    multi = rc.replay_oracle_actions(by_chunk, verify, MULTI_ACTION)
    fixed = {d: rc.replay_fixed(by_chunk, verify, d) for d in DS}
    fixed_d3 = fixed[3]
    selected = rc.replay_selected_policy(
        by_chunk, verify, lambda: rc.VeriCurveSelectedThreshold(threshold=0.4, probe_interval=16)
    )
    goodput = rc.replay_selected_policy(
        by_chunk, verify, lambda: rc.GoodputUcbPolicy(c=0.02, probe_interval=16)
    )

    workload_label = replay_workload_label(by_chunk, verify)
    best_fixed_per_workload = replay_best_fixed_per_workload(by_chunk, verify)
    best_fixed_mixed_d, best_fixed_mixed = min(
        fixed.items(), key=lambda kv: kv[1]["ms_per_token"]
    )

    return {
        "curve": name,
        "C1_ms": round(verify[1]["ms"], 6),
        "C2_ms": round(verify[2]["ms"], 6),
        "C4_ms": round(verify[4]["ms"], 6),
        "C8_ms": round(verify[8]["ms"], 6),
        "C4_C1": round(verify[4]["ms"] / verify[1]["ms"], 6),
        "C8_C1": round(verify[8]["ms"] / verify[1]["ms"], 6),
        "winner_T1": verify[1]["winner"],
        "winner_T4": verify[4]["winner"],
        "winner_T8": verify[8]["winner"],
        "fixed_d0_ms": round(fixed[0]["ms_per_token"], 6),
        "fixed_d3_ms": round(fixed[3]["ms_per_token"], 6),
        "fixed_d7_ms": round(fixed[7]["ms_per_token"], 6),
        "best_fixed_mixed_d": best_fixed_mixed_d,
        "best_fixed_mixed_ms": round(best_fixed_mixed["ms_per_token"], 6),
        "best_fixed_per_workload_ms": round(best_fixed_per_workload["ms_per_token"], 6),
        "workload_label_ms": round(workload_label["ms_per_token"], 6),
        "two_action_oracle_ms": round(two["ms_per_token"], 6),
        "two_action_oracle_choices": rc.choices_str(two["choices"]),
        "multi_action_oracle_ms": round(multi["ms_per_token"], 6),
        "multi_action_oracle_choices": rc.choices_str(multi["choices"]),
        "multi_vs_two_oracle_gain_pct": round((two["ms_per_token"] / multi["ms_per_token"] - 1.0) * 100.0, 6),
        "selected_t0.4_p16_ms": round(selected["ms_per_token"], 6),
        "selected_choices": rc.choices_str(selected["choices"]),
        "goodput_ucb_ms": round(goodput["ms_per_token"], 6),
        "goodput_choices": rc.choices_str(goodput["choices"]),
        "selected_advantage_vs_goodput_pct": round((goodput["ms_per_token"] / selected["ms_per_token"] - 1.0) * 100.0, 6),
        "selected_speedup_vs_fixed_d3_pct": round((fixed_d3["ms_per_token"] / selected["ms_per_token"] - 1.0) * 100.0, 6),
    }


def replay_workload_label(by_chunk, verify):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    for workload in sorted({k[0] for k in by_chunk}):
        d = 0 if workload in {"chat", "chat_low"} else 3
        res = rc.replay_fixed(by_chunk, verify, d, scope_filter={workload})
        total_cost += res["total_cost_ms"]
        total_tokens += res["total_tokens"]
        choices[d] += res["steps_evaluated"]
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens,
        "choices": dict(sorted(choices.items())),
    }


def replay_best_fixed_per_workload(by_chunk, verify):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    for workload in sorted({k[0] for k in by_chunk}):
        candidates = []
        for d in DS:
            res = rc.replay_fixed(by_chunk, verify, d, scope_filter={workload})
            candidates.append((res["ms_per_token"], d, res))
        _ms, d, res = min(candidates, key=lambda x: x[0])
        total_cost += res["total_cost_ms"]
        total_tokens += res["total_tokens"]
        choices[d] += res["steps_evaluated"]
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens,
        "choices": dict(sorted(choices.items())),
    }


def run_t8_threshold_sweep(base_curve, position_complete):
    rows = []
    for ratio_x100 in range(140, 421, 10):
        ratio = ratio_x100 / 100.0
        curve = clone_verify(base_curve)
        curve[8] = {"ms": ratio * curve[1]["ms"], "winner": f"synthetic_T8_ratio_{ratio:.2f}"}
        row = replay_curve(f"synthetic_T8_ratio_{ratio:.2f}", curve, position_complete)
        row["synthetic_C8_C1"] = ratio
        rows.append(row)
    return rows


def decision_matrix(curve_rows, threshold_rows):
    by_curve = {r["curve"]: r for r in curve_rows}
    current = by_curve["current_best_rows512"]
    split = by_curve["synth_split_T8_from_T4_rows512"]
    rows2048 = by_curve.get("dynamic_plan_family_rows2048_normalized")
    threshold_pass = [
        r for r in threshold_rows
        if float(r["multi_vs_two_oracle_gain_pct"]) >= 5.0
    ]
    max_threshold = threshold_pass[-1] if threshold_pass else None

    plan_synth_pass = (
        float(split["multi_vs_two_oracle_gain_pct"]) >= 5.0
        and float(split["selected_advantage_vs_goodput_pct"]) >= 5.0
    )
    phase_model_pass = (
        max_threshold is not None
        and float(current["multi_vs_two_oracle_gain_pct"]) < 3.0
        and float(split["multi_vs_two_oracle_gain_pct"]) < 3.0
    )
    robustness_pass = (
        rows2048 is not None and float(rows2048["C4_C1"]) <= 1.8
    )

    return [
        {
            "candidate_id": "C1",
            "candidate": "verification_plan_synthesis",
            "core_test": "measured synth_split_T8_from_T4 must make multi-point valuable and beat goodput",
            "key_result": (
                f"split_multi_gain={split['multi_vs_two_oracle_gain_pct']}%; "
                f"split_selected_adv_goodput={split['selected_advantage_vs_goodput_pct']}%"
            ),
            "killer_baseline_result": (
                f"fixed_d3={split['fixed_d3_ms']}; goodput={split['goodput_ucb_ms']}; "
                f"best_fixed_per_workload={split['best_fixed_per_workload_ms']}"
            ),
            "generalization_result": (
                f"rows128_norm_C4_C1={by_curve.get('dynamic_plan_family_rows128_normalized', {}).get('C4_C1', '')}; "
                f"rows2048_norm_C4_C1={rows2048.get('C4_C1', '') if rows2048 else ''}"
            ),
            "decision": "PASS" if plan_synth_pass and robustness_pass else "FAIL_CURRENT_EVIDENCE",
            "falsifier": "current measured/composed T8 plan leaves multi-point gain below 5% or rows2048 ratio above 1.8",
        },
        {
            "candidate_id": "C2",
            "candidate": "phase_transition_model_for_policy_regimes",
            "core_test": "sweep C8/C1 and explain why current policies collapse to d0/d3",
            "key_result": (
                f"max_C8_C1_with_multi_gain_ge5="
                f"{max_threshold['synthetic_C8_C1'] if max_threshold else 'none'}; "
                f"current_C8_C1={current['C8_C1']}; split_C8_C1={split['C8_C1']}"
            ),
            "killer_baseline_result": (
                f"current_goodput_tie={current['selected_advantage_vs_goodput_pct']}%; "
                f"current_multi_gain={current['multi_vs_two_oracle_gain_pct']}%"
            ),
            "generalization_result": (
                "explains rows512 d0/d3 collapse; does not by itself improve rows2048 or beat goodput"
            ),
            "decision": "PROMISING_EXPLANATION_NOT_A_LEVEL" if phase_model_pass else "FAIL",
            "falsifier": "if measured T8/C1 below threshold still does not produce d7, or if goodput-only remains sufficient explanation",
        },
        {
            "candidate_id": "C3",
            "candidate": "working_set_aware_rvv_curve_family",
            "core_test": "same abstraction should retain useful T4/C1 on larger working set",
            "key_result": (
                f"rows2048_norm_C4_C1={rows2048.get('C4_C1', '') if rows2048 else 'missing'}; "
                f"rows2048_abs_C4_C1={by_curve.get('dynamic_plan_family_rows2048_absolute', {}).get('C4_C1', '')}"
            ),
            "killer_baseline_result": "old curve remains near-linear; shaped rows2048 improves old T4 but not enough for broad A-level claim",
            "generalization_result": "rows128 and rows512 pass; rows2048 fails strict <=1.8 gate",
            "decision": "FAIL_CURRENT_EVIDENCE" if not robustness_pass else "PASS",
            "falsifier": "larger working set C4/C1 > 2.5 or policy reverts to no-spec/fixed-only behavior",
        },
        {
            "candidate_id": "C4",
            "candidate": "selected_only_curve_controller",
            "core_test": "selected-only curve-aware control must beat goodput-only by >=5 and reach >=90% oracle",
            "key_result": (
                f"current_selected_adv_goodput={current['selected_advantage_vs_goodput_pct']}%; "
                f"current_selected_speedup_fixed_d3={current['selected_speedup_vs_fixed_d3_pct']}%"
            ),
            "killer_baseline_result": f"goodput={current['goodput_ucb_ms']}; fixed_d3={current['fixed_d3_ms']}",
            "generalization_result": "policy remains two-action; multi-point current gain is zero",
            "decision": "FAIL_CURRENT_EVIDENCE",
            "falsifier": "goodput-only within 3-5% or oracle reach below 90%",
        },
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--position-complete", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--variant-timing", required=True)
    ap.add_argument("--remote-rtile-results", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    position_complete = Path(args.position_complete)
    curves = build_curves(args)
    curve_rows = [replay_curve(name, curve, position_complete) for name, curve in sorted(curves.items())]
    write_csv(out / "innovation_curve_family_replay.csv", curve_rows)

    best512 = rc.load_verify(Path(args.verify), "best")
    threshold_rows = run_t8_threshold_sweep(best512, position_complete)
    write_csv(out / "innovation_t8_threshold_sweep.csv", threshold_rows)

    write_csv(out / "innovation_decision_matrix.csv", decision_matrix(curve_rows, threshold_rows))


if __name__ == "__main__":
    main()
