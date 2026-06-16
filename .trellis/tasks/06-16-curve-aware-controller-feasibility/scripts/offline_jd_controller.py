#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path


DS = [0, 1, 3, 7, 15]
WORKLOADS = ["chat", "code", "rag", "structured", "mixed"]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def load_verify(path):
    old = {}
    best = {}
    winner = {}
    for r in read_csv(path):
        T = int(r["T"])
        old[T] = float(r["C_verify_old_ms"])
        best[T] = float(r["C_verify_best_ms"])
        winner[T] = r["winner_variant"]
    return old, best, winner


def load_draft(path):
    costs = {}
    for r in read_csv(path):
        costs[(r["draft_source"], int(r["d"]))] = float(r["C_draft_ms"])
    return costs


def load_acceptance(path):
    acc = {}
    for r in read_csv(path):
        acc[(r["workload"], r["draft_source"], int(r["d"]))] = {
            "E_accept": float(r["E_accept"]),
            "acceptance_per_draft": float(r["acceptance_per_draft"]),
            "full_accept_rate": float(r["full_accept_rate"]),
        }
    return acc


def load_raw(path):
    rows = []
    for r in read_csv(path):
        rows.append({
            "workload": r["workload"],
            "draft_source": r["draft_source"],
            "d": int(r["d"]),
            "position": int(r["position"]),
            "accepted": int(r["accepted"]),
        })
    return rows


def score(curve, costs, workload, source, d, e_accept):
    if d == 0:
        return curve[1]
    T = 1 + d
    return (curve[T] + costs[(source, d)]) / (1.0 + e_accept)


def format_choices(choices):
    return ";".join(f"{s}:d{d}={n}" for (s, d), n in sorted(choices.items()))


def solve_fractional_oracle(positions, raw_by_work_pos, workload, actions, curve, costs):
    """Minimize total cost / total emitted tokens with per-position future knowledge."""
    if not positions:
        return None

    def action_cost_tokens(pos, action):
        source, d = action
        if d == 0:
            return curve[1], 1
        accepted = raw_by_work_pos[(workload, pos)][(source, d)]
        return curve[1 + d] + costs[(source, d)], 1 + accepted

    # Dinkelbach's method for independent per-position fractional choices.
    lam = curve[1]
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    for _ in range(100):
        total_cost = 0.0
        total_tokens = 0
        choices = defaultdict(int)
        for pos in positions:
            best = None
            for action in actions:
                cost, tokens = action_cost_tokens(pos, action)
                objective = cost - lam * tokens
                if best is None or objective < best[0]:
                    best = (objective, action, cost, tokens)
            _, action, cost, tokens = best
            choices[action] += 1
            total_cost += cost
            total_tokens += tokens
        new_lam = total_cost / total_tokens
        if abs(new_lam - lam) < 1e-12:
            break
        lam = new_lam
    return total_cost, total_tokens, total_cost / total_tokens, choices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--acceptance", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    old_curve, best_curve, winners = load_verify(Path(args.verify))
    costs = load_draft(Path(args.draft))
    acc = load_acceptance(Path(args.acceptance))
    raw = load_raw(Path(args.raw))
    sources = sorted({s for s, _ in costs})

    detail = []
    for workload in WORKLOADS:
        detail.append({
            "workload": workload,
            "draft_source": "none",
            "d": 0,
            "T": 1,
            "E_accept": 0.0,
            "C_draft_ms": 0.0,
            "J_old_ms_per_token": round(old_curve[1], 6),
            "J_new_ms_per_token": round(best_curve[1], 6),
            "winner_variant": winners[1],
        })
        for source in sources:
            for d in [1, 3, 7, 15]:
                a = acc[(workload, source, d)]
                detail.append({
                    "workload": workload,
                    "draft_source": source,
                    "d": d,
                    "T": 1 + d,
                    "E_accept": a["E_accept"],
                    "C_draft_ms": costs[(source, d)],
                    "J_old_ms_per_token": round(score(old_curve, costs, workload, source, d, a["E_accept"]), 6),
                    "J_new_ms_per_token": round(score(best_curve, costs, workload, source, d, a["E_accept"]), 6),
                    "winner_variant": winners[1 + d],
                })

    write_csv(out / "Jd_offline_prediction.csv", detail)

    summary = []
    for workload in WORKLOADS:
        rows = [r for r in detail if r["workload"] == workload]
        old_best = min(rows, key=lambda r: float(r["J_old_ms_per_token"]))
        new_best = min(rows, key=lambda r: float(r["J_new_ms_per_token"]))
        no_spec = [r for r in rows if int(r["d"]) == 0][0]
        fixed_d3_rows = [r for r in rows if int(r["d"]) == 3]
        fixed_d3 = min(fixed_d3_rows, key=lambda r: float(r["J_new_ms_per_token"]))
        speedup_no_spec = float(no_spec["J_new_ms_per_token"]) / float(new_best["J_new_ms_per_token"])
        speedup_fixed_d3 = float(fixed_d3["J_new_ms_per_token"]) / float(new_best["J_new_ms_per_token"])
        summary.append({
            "workload": workload,
            "best_d_old_curve": old_best["d"],
            "best_source_old_curve": old_best["draft_source"],
            "best_J_old_ms": old_best["J_old_ms_per_token"],
            "best_d_new_curve": new_best["d"],
            "best_source_new_curve": new_best["draft_source"],
            "best_J_new_ms": new_best["J_new_ms_per_token"],
            "best_d_fixed_default": 3,
            "best_source_fixed_d3": fixed_d3["draft_source"],
            "fixed_d3_J_new_ms": fixed_d3["J_new_ms_per_token"],
            "predicted_speedup_vs_no_spec": round(speedup_no_spec, 6),
            "predicted_speedup_vs_fixed_d3": round(speedup_fixed_d3, 6),
        })

    write_csv(out / "Jd_offline_summary.csv", summary)

    # Oracle uses per-position actual accepted prefix and may choose source/d per
    # position. The score is total cost divided by total emitted tokens, matching
    # the J(d) ratio used above.
    raw_by_work_pos = defaultdict(dict)
    for r in raw:
        raw_by_work_pos[(r["workload"], r["position"])][(r["draft_source"], r["d"])] = r["accepted"]

    oracle_rows = []
    actions = [("none", 0)] + [(source, d) for source in sources for d in [1, 3, 7, 15]]
    expected = len(sources) * 4
    for workload in WORKLOADS:
        positions = []
        for (wl, pos), candidates in raw_by_work_pos.items():
            if wl == workload and len(candidates) == expected:
                positions.append(pos)
        positions = sorted(positions)
        if not positions:
            continue
        total_cost, total_tokens, oracle_score, choices = solve_fractional_oracle(
            positions, raw_by_work_pos, workload, actions, best_curve, costs
        )
        oracle_rows.append({
            "workload": workload,
            "common_positions": len(positions),
            "oracle_total_cost_ms": round(total_cost, 6),
            "oracle_total_tokens": total_tokens,
            "oracle_J_new_ms": round(oracle_score, 6),
            "oracle_choices": format_choices(choices),
            "method": "fractional_total_cost_over_total_tokens_common_positions",
        })
    write_csv(out / "oracle_by_workload.csv", oracle_rows)

    # Mixed-workload controller baselines use the four real buckets, not the
    # already concatenated mixed text, to avoid double-counting.
    eval_workloads = ["chat", "code", "rag", "structured"]
    by_w = {r["workload"]: r for r in summary}
    no_spec_mixed = sum(best_curve[1] for _ in eval_workloads) / len(eval_workloads)
    vericurve_mixed = sum(float(by_w[w]["best_J_new_ms"]) for w in eval_workloads) / len(eval_workloads)

    fixed_candidates = []
    for d in DS:
        if d == 0:
            fixed_candidates.append(("none", 0, no_spec_mixed))
            continue
        for source in sources:
            vals = []
            for w in eval_workloads:
                a = acc[(w, source, d)]["E_accept"]
                vals.append(score(best_curve, costs, w, source, d, a))
            fixed_candidates.append((source, d, sum(vals) / len(vals)))
    fixed_source, fixed_d, fixed_score = min(fixed_candidates, key=lambda x: x[2])

    goodput_vals = []
    for w in eval_workloads:
        best_acc = max(
            (acc[(w, source, d)]["E_accept"], source, d)
            for source in sources
            for d in [1, 3, 7, 15]
        )
        _, source, d = best_acc
        goodput_vals.append(score(best_curve, costs, w, source, d, acc[(w, source, d)]["E_accept"]))
    goodput_score = sum(goodput_vals) / len(goodput_vals)

    oracle_by_w = {r["workload"]: float(r["oracle_J_new_ms"]) for r in oracle_rows}
    oracle_mixed = sum(oracle_by_w[w] for w in eval_workloads) / len(eval_workloads)

    controller = [{
        "baseline": "B0_no_speculation",
        "ms_per_token": round(no_spec_mixed, 6),
        "relative_to_vericurve": round(no_spec_mixed / vericurve_mixed, 6),
        "notes": "d=0 for all workloads",
    }, {
        "baseline": "B2_fixed_d3",
        "ms_per_token": round(min(x[2] for x in fixed_candidates if x[1] == 3), 6),
        "relative_to_vericurve": round(min(x[2] for x in fixed_candidates if x[1] == 3) / vericurve_mixed, 6),
        "notes": "best source with d=3 over mixed workloads",
    }, {
        "baseline": "B4_offline_best_fixed_mixed",
        "ms_per_token": round(fixed_score, 6),
        "relative_to_vericurve": round(fixed_score / vericurve_mixed, 6),
        "notes": f"single fixed policy {fixed_source} d={fixed_d}",
    }, {
        "baseline": "B5_goodput_only_adaptive",
        "ms_per_token": round(goodput_score, 6),
        "relative_to_vericurve": round(goodput_score / vericurve_mixed, 6),
        "notes": "per workload choose max E_accept, ignoring costs",
    }, {
        "baseline": "B6_Vericurve_RV_offline",
        "ms_per_token": round(vericurve_mixed, 6),
        "relative_to_vericurve": 1.0,
        "notes": "per workload choose min J_new",
    }, {
        "baseline": "B7_oracle",
        "ms_per_token": round(oracle_mixed, 6),
        "relative_to_vericurve": round(oracle_mixed / vericurve_mixed, 6),
        "notes": "per position choose best source/d with actual future acceptance",
    }]
    write_csv(out / "controller_go_nogo.csv", controller)


if __name__ == "__main__":
    main()
