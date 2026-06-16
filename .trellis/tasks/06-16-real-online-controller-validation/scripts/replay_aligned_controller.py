#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path


DS = [0, 1, 3, 7]
ALPHA = 0.3
SWITCH_MARGIN = 0.05
MIN_DWELL = 2


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_verify(path):
    out = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            T = int(row["T"])
            out[T] = {
                "ms": float(row["C_verify_best_ms"]),
                "winner": row["winner_variant"],
            }
    return out


def row_cost(row, verify):
    d = int(row["candidate_d"])
    T = 1 + d
    return verify[T]["ms"] + float(row["trace_draft_us"]) / 1000.0


def row_tokens(row):
    return 1 + int(row["accepted_count"])


def score_rows(rows, verify, chooser):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    for step_key, candidates in rows:
        chosen = chooser(step_key, candidates)
        d = int(chosen["candidate_d"])
        choices[d] += 1
        total_cost += row_cost(chosen, verify)
        total_tokens += row_tokens(chosen)
    return total_cost, total_tokens, total_cost / total_tokens, dict(sorted(choices.items()))


def dinkelbach_oracle(rows, verify):
    lam = min(verify[1 + d]["ms"] / (1 + d) for d in DS)
    final_choices = {}
    total_cost = 0.0
    total_tokens = 0
    for _ in range(100):
        total_cost = 0.0
        total_tokens = 0
        choices = defaultdict(int)
        for _, candidates in rows:
            best = None
            for d, cand in candidates.items():
                c = row_cost(cand, verify)
                t = row_tokens(cand)
                obj = c - lam * t
                if best is None or obj < best[0]:
                    best = (obj, d, cand, c, t)
            _, d, _, c, t = best
            choices[d] += 1
            total_cost += c
            total_tokens += t
        new_lam = total_cost / total_tokens
        final_choices = dict(sorted(choices.items()))
        if abs(new_lam - lam) < 1e-12:
            break
        lam = new_lam
    return total_cost, total_tokens, total_cost / total_tokens, final_choices


def fixed_chooser(d):
    return lambda _step, candidates: candidates[d]


def goodput_chooser(_step, candidates):
    return max(candidates.values(), key=lambda r: (int(r["accepted_count"]), int(r["candidate_d"])))


def ewma_full_info_score(rows, verify):
    # Full-information replay: after each aligned step, all candidate acceptances
    # are visible to the replay. This is an upper-bound proxy for an online EWMA
    # controller, not a deployable selected-only controller.
    ewma = {d: 0.0 for d in DS}
    current_d = 0
    dwell = 0
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    trace = []
    for step_key, candidates in rows:
        scores = {}
        for d in DS:
            T = 1 + d
            avg_draft_ms = float(candidates[d]["trace_draft_us"]) / 1000.0
            scores[d] = (verify[T]["ms"] + avg_draft_ms) / (1.0 + ewma[d])
        best_d = min(DS, key=lambda d: scores[d])
        switch_reason = "hold"
        if best_d != current_d:
            if dwell >= MIN_DWELL and scores[best_d] <= scores[current_d] * (1.0 - SWITCH_MARGIN):
                current_d = best_d
                dwell = 0
                switch_reason = "switch_margin"
            else:
                switch_reason = "blocked_margin_or_dwell"
        chosen = candidates[current_d]
        total_cost += row_cost(chosen, verify)
        total_tokens += row_tokens(chosen)
        choices[current_d] += 1
        trace.append({
            "workload": step_key[0],
            "chunk_id": step_key[1],
            "step_id": step_key[2],
            "pseudo_position": step_key[3],
            "selected_d": current_d,
            "actual_accept": chosen["accepted_count"],
            "score_d0": round(scores[0], 6),
            "score_d1": round(scores[1], 6),
            "score_d3": round(scores[3], 6),
            "score_d7": round(scores[7], 6),
            "switch_reason": switch_reason,
            "method": "full_information_ewma_replay_upper_bound",
        })
        for d in DS:
            ewma[d] = (1.0 - ALPHA) * ewma[d] + ALPHA * int(candidates[d]["accepted_count"])
        dwell += 1
    return total_cost, total_tokens, total_cost / total_tokens, dict(sorted(choices.items())), trace


def load_aligned(artifacts, verify):
    combined = []
    by_workload = defaultdict(dict)
    for path in sorted(artifacts.glob("aligned_candidate_*.csv")):
        if path.name.endswith("_commit_d3.csv"):
            continue
        workload = path.stem.removeprefix("aligned_candidate_")
        for row in read_csv(path):
            d = int(row["candidate_d"])
            step_key = (workload, int(row["chunk_id"]), int(row["step_id"]), int(row["pseudo_position"]))
            out = {
                "workload": workload,
                "chunk_id": row["chunk_id"],
                "step_id": row["step_id"],
                "pseudo_position": row["pseudo_position"],
                "candidate_d": d,
                "T": 1 + d,
                "drafted_count": row["drafted_count"],
                "accepted_count": row["accepted_count"],
                "target_available": row["target_available"],
                "trace_draft_us": row["trace_draft_us"],
                "C_verify_best_ms": verify[1 + d]["ms"],
                "winner_variant": verify[1 + d]["winner"],
                "step_cost_ms": round(verify[1 + d]["ms"] + float(row["trace_draft_us"]) / 1000.0, 9),
                "emitted_tokens": 1 + int(row["accepted_count"]),
                "method": "aligned_same_pseudo_position_lookup_stats",
            }
            combined.append(out)
            by_workload[workload][step_key] = by_workload[workload].get(step_key, {})
            by_workload[workload][step_key][d] = out

    grouped = {}
    for workload, steps in by_workload.items():
        complete = []
        for key, candidates in sorted(steps.items()):
            if set(candidates.keys()) == set(DS):
                complete.append((key, candidates))
        grouped[workload] = complete
    return combined, grouped


def choices_str(choices):
    return ";".join(f"d{d}={n}" for d, n in sorted(choices.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    artifacts = Path(args.artifacts)
    out = Path(args.out)
    verify = load_verify(Path(args.verify))
    combined, grouped = load_aligned(artifacts, verify)
    write_csv(out / "aligned_candidate_trace.csv", combined)

    workload_rows = []
    all_steps = []
    for workload, rows in grouped.items():
        all_steps.extend(rows)
        for d in DS:
            c, t, s, choices = score_rows(rows, verify, fixed_chooser(d))
            workload_rows.append({
                "scope": workload,
                "baseline": f"fixed_d{d}",
                "ms_per_token": round(s, 6),
                "total_cost_ms": round(c, 6),
                "total_tokens": t,
                "choices": choices_str(choices),
                "method": "aligned_replay",
            })
        c, t, s, choices = score_rows(rows, verify, goodput_chooser)
        workload_rows.append({
            "scope": workload,
            "baseline": "goodput_only",
            "ms_per_token": round(s, 6),
            "total_cost_ms": round(c, 6),
            "total_tokens": t,
            "choices": choices_str(choices),
            "method": "aligned_replay",
        })
        c, t, s, choices = dinkelbach_oracle(rows, verify)
        workload_rows.append({
            "scope": workload,
            "baseline": "oracle",
            "ms_per_token": round(s, 6),
            "total_cost_ms": round(c, 6),
            "total_tokens": t,
            "choices": choices_str(choices),
            "method": "aligned_replay_total_cost_over_total_tokens",
        })
        c, t, s, choices, _ = ewma_full_info_score(rows, verify)
        workload_rows.append({
            "scope": workload,
            "baseline": "vericurve_ewma_full_info",
            "ms_per_token": round(s, 6),
            "total_cost_ms": round(c, 6),
            "total_tokens": t,
            "choices": choices_str(choices),
            "method": "upper_bound_replay",
        })
    write_csv(out / "aligned_replay_by_workload.csv", workload_rows)

    mixed_rows = []
    fixed_labels = {
        0: "B0_no_speculation",
        1: "B1_fixed_d1",
        3: "B2_fixed_d3",
        7: "B3_fixed_d7",
    }
    for d in DS:
        c, t, s, choices = score_rows(all_steps, verify, fixed_chooser(d))
        mixed_rows.append((fixed_labels[d], c, t, s, choices, "aligned_replay"))

    fixed_scores = []
    for d in DS:
        c, t, s, choices = score_rows(all_steps, verify, fixed_chooser(d))
        fixed_scores.append((d, c, t, s, choices))
    best_fixed_mixed = min(fixed_scores, key=lambda x: x[3])
    mixed_rows.append((
        "B4_offline_best_fixed_mixed",
        best_fixed_mixed[1],
        best_fixed_mixed[2],
        best_fixed_mixed[3],
        best_fixed_mixed[4],
        f"best fixed d={best_fixed_mixed[0]} over pooled aligned trace",
    ))

    # Best fixed per workload, then pooled.
    total_c = 0.0
    total_t = 0
    choices = defaultdict(int)
    for workload, rows in grouped.items():
        best = min((score_rows(rows, verify, fixed_chooser(d)) + (d,) for d in DS), key=lambda x: x[2])
        c, t, _s, ch, d = best
        total_c += c
        total_t += t
        choices[d] += len(rows)
    mixed_rows.append(("B5_offline_best_fixed_per_workload", total_c, total_t, total_c / total_t, dict(choices), "best fixed d per workload"))

    c, t, s, choices = score_rows(all_steps, verify, goodput_chooser)
    mixed_rows.append(("B6_goodput_only", c, t, s, choices, "per step choose max accepted_count ignoring cost"))

    c, t, s, choices, ewma_trace = ewma_full_info_score(all_steps, verify)
    mixed_rows.append(("B7_Vericurve_EWMA_full_info", c, t, s, choices, "upper bound: updates all candidate EWMAs from aligned trace"))
    write_csv(out / "online_ewma_replay_trace.csv", ewma_trace)

    c, t, s, choices = dinkelbach_oracle(all_steps, verify)
    mixed_rows.append(("B8_oracle", c, t, s, choices, "per step oracle with total cost / total tokens objective"))

    fixed_d3 = next(r for r in mixed_rows if r[0] == "B2_fixed_d3")[3]
    oracle = next(r for r in mixed_rows if r[0] == "B8_oracle")[3]
    summary = []
    for name, c, t, s, choices, notes in mixed_rows:
        summary.append({
            "baseline": name,
            "ms_per_token": round(s, 6),
            "relative_to_fixed_d3": round(s / fixed_d3, 6),
            "oracle_reach": round(oracle / s, 6),
            "total_cost_ms": round(c, 6),
            "total_tokens": t,
            "choices": choices_str(choices),
            "notes": notes,
        })
    write_csv(out / "aligned_replay_summary.csv", summary)


if __name__ == "__main__":
    main()
