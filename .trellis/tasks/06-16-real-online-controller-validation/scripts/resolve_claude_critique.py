#!/usr/bin/env python3
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import replay_commit_aware as base  # noqa: E402


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
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_verify(path, mode):
    col = {
        "old": "C_verify_old_ms",
        "new": "C_verify_new_ms",
        "best": "C_verify_best_ms",
    }[mode]
    verify = {}
    for row in read_csv(path):
        t = int(row["T"])
        if mode == "old":
            winner = "old_vecdot_nrc1"
        elif mode == "new":
            winner = row["winner_variant"] if row["winner_variant"] != "old_vecdot_nrc1" else "new_candidate"
        else:
            winner = row["winner_variant"]
        verify[t] = {
            "ms": float(row[col]),
            "winner": winner,
        }
    return verify


def choices_str(choices):
    return ";".join(f"d{d}={n}" for d, n in sorted(choices.items()))


def action_label(actions):
    return "{" + ",".join(f"d{d}" for d in actions) + "}"


def replay_fixed(by_chunk, verify, d, scope_filter=None):
    return base.replay_policy(by_chunk, lambda: base.FixedPolicy(d), verify, scope_filter=scope_filter)


def replay_oracle_actions(by_chunk, verify, actions, scope_filter=None, trace_rows=None, policy_name=None):
    lam = min(verify[1 + d]["ms"] / (1 + d) for d in actions)
    final_choice_maps = {}
    for _ in range(100):
        total_cost = 0.0
        total_tokens = 0
        choice_maps = {}
        for key, positions in sorted(by_chunk.items()):
            workload, _chunk_id = key
            if scope_filter and workload not in scope_filter:
                continue
            cmap = oracle_for_chunk_actions(positions, verify, actions, lam)
            choice_maps[key] = cmap
            pos = min(positions)
            max_pos = max(positions)
            while pos in positions and pos in cmap:
                d, next_pos = cmap[pos]
                row = positions[pos][d]
                total_cost += base.row_cost(row, verify)
                total_tokens += base.row_tokens(row)
                if next_pos > max_pos:
                    break
                pos = next_pos
        if not total_tokens:
            break
        new_lam = total_cost / total_tokens
        final_choice_maps = choice_maps
        if abs(new_lam - lam) < 1e-12:
            lam = new_lam
            break
        lam = new_lam

    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    steps = 0
    chunks = 0
    completed = 0
    missing = 0
    terminal = 0
    for key, positions in sorted(by_chunk.items()):
        workload, chunk_id = key
        if scope_filter and workload not in scope_filter:
            continue
        chunks += 1
        pos = min(positions)
        max_pos = max(positions)
        cmap = final_choice_maps.get(key, {})
        while pos in positions and pos in cmap:
            d, next_pos = cmap[pos]
            row = positions[pos][d]
            cost = base.row_cost(row, verify)
            tokens = base.row_tokens(row)
            total_cost += cost
            total_tokens += tokens
            choices[d] += 1
            steps += 1
            if trace_rows is not None:
                trace_rows.append({
                    "policy": policy_name or f"oracle_{action_label(actions)}",
                    "workload": workload,
                    "chunk_id": chunk_id,
                    "position": pos,
                    "selected_d": d,
                    "accepted_count": row["accepted_count"],
                    "emitted_tokens": tokens,
                    "step_cost_ms": round(cost, 9),
                    "reason": "oracle_dp",
                    "observed_reward_tokens_per_ms": round(tokens / cost, 9) if cost else "",
                })
            if next_pos > max_pos:
                terminal += 1
                completed += 1
                break
            pos = next_pos
        else:
            missing += 1
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens if total_tokens else math.nan,
        "choices": dict(sorted(choices.items())),
        "missing_transitions": missing,
        "terminal_transitions": terminal,
        "steps_evaluated": steps,
        "chunks_started": chunks,
        "completed_chunks": completed,
    }


def oracle_for_chunk_actions(positions, verify, actions, lam):
    max_pos = max(positions)
    ordered = sorted(positions, reverse=True)
    dp = {max_pos + 1: 0.0}
    choice = {}
    for pos in ordered:
        best = None
        for d in actions:
            if d not in positions[pos]:
                continue
            row = positions[pos][d]
            tokens = base.row_tokens(row)
            nxt = pos + tokens
            future_key = nxt if nxt <= max_pos else max_pos + 1
            if future_key not in dp:
                continue
            val = base.row_cost(row, verify) - lam * tokens + dp[future_key]
            if best is None or val < best[0]:
                best = (val, d, nxt)
        if best is not None:
            dp[pos] = best[0]
            choice[pos] = (best[1], best[2])
    return choice


class VeriCurveSelectedThreshold:
    policy_class = "curve_aware_threshold"
    observability = "selected_only"
    arms = TWO_ACTION

    def __init__(self, threshold=0.4, alpha=0.3, probe_interval=16, min_samples=4, switch_margin=0.05):
        self.threshold = threshold
        self.alpha = alpha
        self.probe_interval = probe_interval
        self.min_samples = min_samples
        self.switch_margin = switch_margin
        self.samples = 0
        self.ewma_accept = 0.0
        self.steps = 0
        self.name = f"vericurve_selected_t{threshold}_p{probe_interval}"
        self.params = (
            f"threshold={threshold};alpha={alpha};probe_interval={probe_interval};"
            f"min_samples={min_samples};switch_margin={switch_margin}"
        )

    def select(self, candidates, workload):
        self.steps += 1
        if self.samples < self.min_samples:
            return 3, "warmup_d3"
        if self.probe_interval > 0 and self.steps % self.probe_interval == 0:
            return 3, "periodic_d3_probe"
        if self.ewma_accept >= self.threshold * (1.0 + self.switch_margin):
            return 3, "curve_threshold_accept"
        return 0, "curve_threshold_fallback_d0"

    def update(self, chosen, cost=None, tokens=None):
        if int(chosen["candidate_d"]) == 3:
            observed = int(chosen["accepted_count"])
            self.ewma_accept = (1.0 - self.alpha) * self.ewma_accept + self.alpha * observed
            self.samples += 1


class GoodputEwmaPolicy:
    policy_class = "goodput_only_ewma"
    observability = "selected_only"
    arms = TWO_ACTION

    def __init__(self, alpha=0.3, probe_interval=16, min_samples_per_arm=4, switch_margin=0.05):
        self.alpha = alpha
        self.probe_interval = probe_interval
        self.min_samples_per_arm = min_samples_per_arm
        self.switch_margin = switch_margin
        self.steps = 0
        self.samples = {d: 0 for d in self.arms}
        self.reward = {d: None for d in self.arms}
        self.next_probe = 0
        self.name = f"goodput_ewma_p{probe_interval}"
        self.params = (
            f"reward=emitted_tokens/observed_cost;alpha={alpha};probe_interval={probe_interval};"
            f"min_samples_per_arm={min_samples_per_arm};switch_margin={switch_margin}"
        )

    def select(self, candidates, workload):
        self.steps += 1
        for d in self.arms:
            if self.samples[d] < self.min_samples_per_arm:
                return d, f"warmup_d{d}"
        greedy = max(self.arms, key=lambda d: (self.reward[d], d))
        other = 0 if greedy == 3 else 3
        if self.probe_interval > 0 and self.steps % self.probe_interval == 0:
            return other, f"periodic_probe_d{other}"
        if self.reward[greedy] >= (self.reward[other] or 0.0) * (1.0 + self.switch_margin):
            return greedy, "goodput_ewma_greedy"
        return min(self.arms), "goodput_ewma_margin_fallback"

    def update(self, chosen, cost=None, tokens=None):
        d = int(chosen["candidate_d"])
        reward = (tokens / cost) if cost else 0.0
        if self.reward[d] is None:
            self.reward[d] = reward
        else:
            self.reward[d] = (1.0 - self.alpha) * self.reward[d] + self.alpha * reward
        self.samples[d] += 1


class GoodputUcbPolicy:
    policy_class = "goodput_only_ucb"
    observability = "selected_only"
    arms = TWO_ACTION

    def __init__(self, c=0.02, probe_interval=16, min_samples_per_arm=4):
        self.c = c
        self.probe_interval = probe_interval
        self.min_samples_per_arm = min_samples_per_arm
        self.steps = 0
        self.samples = {d: 0 for d in self.arms}
        self.reward_sum = {d: 0.0 for d in self.arms}
        self.name = f"goodput_ucb_c{c}_p{probe_interval}"
        self.params = (
            f"reward=emitted_tokens/observed_cost;c={c};probe_interval={probe_interval};"
            f"min_samples_per_arm={min_samples_per_arm}"
        )

    def select(self, candidates, workload):
        self.steps += 1
        for d in self.arms:
            if self.samples[d] < self.min_samples_per_arm:
                return d, f"warmup_d{d}"
        if self.probe_interval > 0 and self.steps % self.probe_interval == 0:
            greedy = max(self.arms, key=lambda d: (self.reward_sum[d] / self.samples[d], d))
            other = 0 if greedy == 3 else 3
            return other, f"periodic_probe_d{other}"
        total = sum(self.samples.values())
        def score(d):
            mean = self.reward_sum[d] / self.samples[d]
            bonus = self.c * math.sqrt(math.log(max(total, 2)) / self.samples[d])
            return mean + bonus
        d = max(self.arms, key=lambda x: (score(x), x))
        return d, "goodput_ucb"

    def update(self, chosen, cost=None, tokens=None):
        d = int(chosen["candidate_d"])
        reward = (tokens / cost) if cost else 0.0
        self.reward_sum[d] += reward
        self.samples[d] += 1


def replay_selected_policy(by_chunk, verify, policy_factory, scope_filter=None, trace_rows=None):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    missing = 0
    terminal = 0
    steps = 0
    chunks = 0
    completed = 0
    for (workload, chunk_id), positions in sorted(by_chunk.items()):
        if scope_filter and workload not in scope_filter:
            continue
        chunks += 1
        policy = policy_factory()
        pos = min(positions)
        max_pos = max(positions)
        while pos in positions:
            candidates = positions[pos]
            if set(policy.arms) - set(candidates):
                missing += 1
                break
            d, reason = policy.select(candidates, workload)
            chosen = candidates[d]
            cost = base.row_cost(chosen, verify)
            tokens = base.row_tokens(chosen)
            total_cost += cost
            total_tokens += tokens
            choices[d] += 1
            steps += 1
            reward = tokens / cost if cost else 0.0
            if trace_rows is not None:
                trace_rows.append({
                    "policy": policy.name,
                    "workload": workload,
                    "chunk_id": chunk_id,
                    "position": pos,
                    "selected_d": d,
                    "accepted_count": chosen["accepted_count"],
                    "emitted_tokens": tokens,
                    "step_cost_ms": round(cost, 9),
                    "reason": reason,
                    "observed_reward_tokens_per_ms": round(reward, 9),
                })
            policy.update(chosen, cost=cost, tokens=tokens)
            next_pos = pos + tokens
            if next_pos > max_pos:
                terminal += 1
                completed += 1
                break
            if next_pos not in positions:
                missing += 1
                break
            pos = next_pos
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens if total_tokens else math.nan,
        "choices": dict(sorted(choices.items())),
        "missing_transitions": missing,
        "terminal_transitions": terminal,
        "steps_evaluated": steps,
        "chunks_started": chunks,
        "completed_chunks": completed,
    }


def metric_row(scope, policy, policy_class, observability, arms, result, fixed_d3_ms, oracle_ms, params="", notes=""):
    return {
        "scope": scope,
        "policy": policy,
        "policy_class": policy_class,
        "observability": observability,
        "arms": ",".join(f"d{d}" for d in arms),
        "ms_per_token": round(result["ms_per_token"], 6),
        "relative_to_fixed_d3": round(result["ms_per_token"] / fixed_d3_ms, 6) if fixed_d3_ms else "",
        "oracle_reach": round(oracle_ms / result["ms_per_token"], 6) if oracle_ms else "",
        "total_cost_ms": round(result["total_cost_ms"], 6),
        "total_tokens": result["total_tokens"],
        "steps_evaluated": result["steps_evaluated"],
        "choices": choices_str(result["choices"]),
        "missing_transitions": result["missing_transitions"],
        "terminal_transitions": result["terminal_transitions"],
        "chunks_started": result["chunks_started"],
        "completed_chunks": result["completed_chunks"],
        "low_acceptance_ms_per_token": "",
        "low_acceptance_regression_vs_fixed_d0_pct": "",
        "probe_like_decision_pct": "",
        "controller_overhead_pct": "not_measured_replay_only",
        "parameters": params,
        "notes": notes,
    }


def best_fixed_for_actions(by_chunk, verify, actions, scope_filter=None):
    rows = []
    for d in actions:
        res = replay_fixed(by_chunk, verify, d, scope_filter=scope_filter)
        rows.append((res["ms_per_token"], d, res))
    return min(rows, key=lambda x: x[0]), rows


def policy_interpretation(workload, old_best_d, new_best_d):
    low = workload in {"chat", "chat_low"}
    if old_best_d in {0, 1} and new_best_d == 3:
        return "regime_shift_to_speculation"
    if low and new_best_d in {0, 1}:
        return "low_acceptance_stays_no_spec"
    if old_best_d == new_best_d == 3:
        return "already_speculation_favorable"
    if new_best_d == 7:
        return "new_curve_over_speculates_check_T8"
    return "mixed_or_no_clear_shift"


def run_regime_shift(by_chunk, old_verify, best_verify):
    rows = []
    workloads = sorted({k[0] for k in by_chunk})
    for workload in workloads:
        scope = {workload}
        (old_best_ms, old_best_d, _old_best), old_fixed_rows = best_fixed_for_actions(
            by_chunk, old_verify, MULTI_ACTION, scope_filter=scope
        )
        (new_best_ms, new_best_d, _new_best), new_fixed_rows = best_fixed_for_actions(
            by_chunk, best_verify, MULTI_ACTION, scope_filter=scope
        )
        old_by_d = {d: res for _ms, d, res in old_fixed_rows}
        new_by_d = {d: res for _ms, d, res in new_fixed_rows}
        no_spec_new = new_by_d[0]["ms_per_token"]
        rows.append({
            "workload": workload,
            "old_curve_best_d": old_best_d,
            "new_curve_best_d": new_best_d,
            "old_curve_best_ms_per_token": round(old_best_ms, 6),
            "new_curve_best_ms_per_token": round(new_best_ms, 6),
            "fixed_d3_cost_old": round(old_by_d[3]["ms_per_token"], 6),
            "fixed_d3_cost_new": round(new_by_d[3]["ms_per_token"], 6),
            "no_spec_cost": round(no_spec_new, 6),
            "new_vs_old_best_speedup": round(old_best_ms / new_best_ms, 6) if new_best_ms else "",
            "policy_interpretation": policy_interpretation(workload, old_best_d, new_best_d),
        })
    return rows


def run_action_value(by_chunk, verify):
    rows = []
    scopes = [("mixed", None)] + [(w, {w}) for w in sorted({k[0] for k in by_chunk})]
    for scope_name, scope_filter in scopes:
        two_oracle = replay_oracle_actions(by_chunk, verify, TWO_ACTION, scope_filter=scope_filter)
        multi_oracle = replay_oracle_actions(by_chunk, verify, MULTI_ACTION, scope_filter=scope_filter)
        (two_best_ms, two_best_d, _), _two_fixed = best_fixed_for_actions(
            by_chunk, verify, TWO_ACTION, scope_filter=scope_filter
        )
        (multi_best_ms, multi_best_d, _), fixed_rows = best_fixed_for_actions(
            by_chunk, verify, MULTI_ACTION, scope_filter=scope_filter
        )
        by_d = {d: res for _ms, d, res in fixed_rows}
        gain = (two_oracle["ms_per_token"] / multi_oracle["ms_per_token"] - 1.0) * 100.0
        d7_reason = classify_d7(by_d)
        rows.append({
            "scope": scope_name,
            "two_action_oracle_ms_per_token": round(two_oracle["ms_per_token"], 6),
            "multi_action_oracle_ms_per_token": round(multi_oracle["ms_per_token"], 6),
            "multi_vs_two_oracle_gain_pct": round(gain, 6),
            "two_action_oracle_choices": choices_str(two_oracle["choices"]),
            "multi_action_oracle_choices": choices_str(multi_oracle["choices"]),
            "two_action_best_fixed_d": two_best_d,
            "two_action_best_fixed_ms_per_token": round(two_best_ms, 6),
            "multi_action_best_fixed_d": multi_best_d,
            "multi_action_best_fixed_ms_per_token": round(multi_best_ms, 6),
            "fixed_d0_ms_per_token": round(by_d[0]["ms_per_token"], 6),
            "fixed_d1_ms_per_token": round(by_d[1]["ms_per_token"], 6),
            "fixed_d3_ms_per_token": round(by_d[3]["ms_per_token"], 6),
            "fixed_d7_ms_per_token": round(by_d[7]["ms_per_token"], 6),
            "d1_or_d7_selected_by_oracle": any(d in multi_oracle["choices"] for d in [1, 7]),
            "d7_failure_reason": d7_reason,
        })
    return rows


def classify_d7(by_d):
    d7 = by_d[7]["ms_per_token"]
    best = min(res["ms_per_token"] for res in by_d.values())
    d3 = by_d[3]["ms_per_token"]
    if d7 > d3 * 1.25:
        return "T8_verify_cost_dominates"
    if d7 > best * 1.10:
        return "acceptance_gain_insufficient"
    return "not_failed_or_close"


def run_selected_only(by_chunk, verify):
    trace = []
    summary = []
    low_scope = {"chat", "chat_low"}
    fixed_d3 = replay_fixed(by_chunk, verify, 3)
    fixed_d0 = replay_fixed(by_chunk, verify, 0)
    low_fixed_d0 = replay_fixed(by_chunk, verify, 0, scope_filter=low_scope)
    oracle = replay_oracle_actions(by_chunk, verify, MULTI_ACTION)
    fixed_d3_ms = fixed_d3["ms_per_token"]
    oracle_ms = oracle["ms_per_token"]
    summary.append(metric_row(
        "mixed", "fixed_d0", "fixed", "fixed", [0], fixed_d0, fixed_d3_ms, oracle_ms, "d=0",
        "no speculation baseline"
    ))
    summary.append(metric_row(
        "mixed", "fixed_d3", "fixed", "fixed", [3], fixed_d3, fixed_d3_ms, oracle_ms, "d=3",
        "strong fixed speculation baseline"
    ))
    summary.append(metric_row(
        "mixed", "oracle_multipoint", "oracle", "full_candidate_info", MULTI_ACTION, oracle, fixed_d3_ms, oracle_ms,
        "actions={0,1,3,7}", "commit-aware DP oracle, not runtime observable"
    ))

    policy_factories = [
        ("vericurve_selected_t0.4_p16", lambda: VeriCurveSelectedThreshold(threshold=0.4, probe_interval=16)),
        ("vericurve_selected_t0.5_p16", lambda: VeriCurveSelectedThreshold(threshold=0.5, probe_interval=16)),
        ("goodput_ewma_p16", lambda: GoodputEwmaPolicy(probe_interval=16)),
        ("goodput_ucb_c0.02_p16", lambda: GoodputUcbPolicy(c=0.02, probe_interval=16)),
        ("goodput_ucb_c0.05_p16", lambda: GoodputUcbPolicy(c=0.05, probe_interval=16)),
    ]
    low_results = {
        "fixed_d0": low_fixed_d0,
        "fixed_d3": replay_fixed(by_chunk, verify, 3, scope_filter=low_scope),
        "oracle_multipoint": replay_oracle_actions(by_chunk, verify, MULTI_ACTION, scope_filter=low_scope),
    }
    for key, factory in policy_factories:
        policy = factory()
        res = replay_selected_policy(by_chunk, verify, factory, trace_rows=trace)
        summary.append(metric_row(
            "mixed", key, policy.policy_class, policy.observability, policy.arms, res, fixed_d3_ms, oracle_ms,
            policy.params, "selected-only commit-aware replay"
        ))
        low_results[key] = replay_selected_policy(by_chunk, verify, factory, scope_filter=low_scope)

    for workload in sorted({k[0] for k in by_chunk}):
        scope = {workload}
        wd3 = replay_fixed(by_chunk, verify, 3, scope_filter=scope)
        woracle = replay_oracle_actions(by_chunk, verify, MULTI_ACTION, scope_filter=scope)
        for key, factory in policy_factories:
            policy = factory()
            res = replay_selected_policy(by_chunk, verify, factory, scope_filter=scope)
            summary.append(metric_row(
                workload, key, policy.policy_class, policy.observability, policy.arms,
                res, wd3["ms_per_token"], woracle["ms_per_token"], policy.params,
                "selected-only commit-aware replay by workload"
            ))

    probe_counts = defaultdict(lambda: {"probe_like": 0, "total": 0})
    for row in trace:
        policy = row["policy"]
        probe_counts[policy]["total"] += 1
        reason = row["reason"]
        if "probe" in reason or "warmup" in reason:
            probe_counts[policy]["probe_like"] += 1

    for row in summary:
        if row["scope"] != "mixed":
            row["controller_overhead_pct"] = "not_measured_replay_only"
            continue
        low = low_results.get(row["policy"])
        if low:
            low_ms = low["ms_per_token"]
            row["low_acceptance_ms_per_token"] = round(low_ms, 6)
            row["low_acceptance_regression_vs_fixed_d0_pct"] = round(
                (low_ms / low_fixed_d0["ms_per_token"] - 1.0) * 100.0, 6
            )
        counts = probe_counts.get(row["policy"])
        if counts and counts["total"]:
            row["probe_like_decision_pct"] = round(counts["probe_like"] / counts["total"] * 100.0, 6)
    return summary, trace


def run_goodput_comparison(selected_rows):
    mixed = [r for r in selected_rows if r["scope"] == "mixed"]
    by_policy = {r["policy"]: r for r in mixed}
    curve_candidates = [r for r in mixed if r["policy"].startswith("vericurve_selected")]
    goodput_candidates = [r for r in mixed if r["policy"].startswith("goodput_")]
    best_curve = min(curve_candidates, key=lambda r: float(r["ms_per_token"]))
    best_goodput = min(goodput_candidates, key=lambda r: float(r["ms_per_token"]))
    fixed_d3 = by_policy["fixed_d3"]
    oracle = by_policy["oracle_multipoint"]
    curve_ms = float(best_curve["ms_per_token"])
    goodput_ms = float(best_goodput["ms_per_token"])
    fixed_ms = float(fixed_d3["ms_per_token"])
    oracle_ms = float(oracle["ms_per_token"])
    return [
        comparison_row("best_curve_aware_selected", best_curve, fixed_ms, oracle_ms, curve_ms, goodput_ms),
        comparison_row("best_goodput_only_selected", best_goodput, fixed_ms, oracle_ms, curve_ms, goodput_ms),
        comparison_row("fixed_d3", fixed_d3, fixed_ms, oracle_ms, curve_ms, goodput_ms),
        comparison_row("oracle_multipoint", oracle, fixed_ms, oracle_ms, curve_ms, goodput_ms),
    ]


def comparison_row(label, row, fixed_ms, oracle_ms, curve_ms, goodput_ms):
    ms = float(row["ms_per_token"])
    return {
        "comparison_label": label,
        "policy": row["policy"],
        "policy_class": row["policy_class"],
        "observability": row["observability"],
        "ms_per_token": round(ms, 6),
        "speedup_vs_fixed_d3_pct": round((fixed_ms / ms - 1.0) * 100.0, 6),
        "oracle_reach": round(oracle_ms / ms, 6),
        "curve_aware_advantage_vs_goodput_pct": round((goodput_ms / curve_ms - 1.0) * 100.0, 6),
        "choices": row["choices"],
        "notes": row["notes"],
    }


def parse_rtile_sections(path):
    matrix = []
    layout = []
    section = None
    fields = None
    with path.open(newline="") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("kind,layout,R,T,"):
                parts = line.split(",")
                fields = parts
                section = "layout" if "C_total_ms" in parts else "matrix"
                continue
            if fields is None:
                continue
            row = dict(zip(fields, next(csv.reader([line]))))
            if section == "matrix":
                matrix.append(row)
            elif section == "layout":
                layout.append(row)
    return matrix, layout


def shaped_working_set_rows(remote_rtile_dir):
    rows = []
    if not remote_rtile_dir:
        return rows
    directory = Path(remote_rtile_dir)
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("rtile_ttile_rows*_r*.csv")):
        matrix, layout = parse_rtile_sections(path)
        if not matrix:
            continue
        sample = matrix[0]
        row_count = int(sample["rows"])
        n = int(sample["n"])
        old_t1 = float(sample["avg_ms"]) / float(sample["ratio_vs_old_t1"])
        old_t4 = None
        best_t1 = old_t1
        best_t4 = None
        winner_t1 = "old_vecdot_nrc1"
        winner_t4 = "old_vecdot_nrc1"
        for r in matrix:
            t = int(r["T"])
            avg_ms = float(r["avg_ms"])
            name = f"R{r['R']}_{r['layout']}"
            if t == 1 and avg_ms < best_t1:
                best_t1 = avg_ms
                winner_t1 = name
            if t == 4:
                candidate_old_t4 = avg_ms / float(r["ratio_vs_old_T"])
                old_t4 = candidate_old_t4 if old_t4 is None else old_t4
                if best_t4 is None or avg_ms < best_t4:
                    best_t4 = avg_ms
                    winner_t4 = name
        for r in layout:
            total_ms = float(r["C_total_ms"])
            name = f"R{r['R']}_{r['layout']}"
            if best_t4 is None or total_ms < best_t4:
                best_t4 = total_ms
                winner_t4 = name
            if old_t4 is None and float(r["ratio_vs_old_T"]) != 0.0:
                old_t4 = total_ms / float(r["ratio_vs_old_T"])
        if best_t4 is None or old_t4 is None:
            continue
        ratio = best_t4 / best_t1
        if row_count > 512:
            evidence_status = "larger_working_set_shaped"
        elif row_count < 512:
            evidence_status = "smaller_working_set_shaped"
        else:
            evidence_status = "current_working_set_shaped_rerun"
        if ratio <= 1.8:
            conclusion = "PASS_ratio_le_1.8"
        elif ratio <= 2.5:
            conclusion = "CONDITIONAL_ratio_gt_1.8_le_2.5"
        else:
            conclusion = "WEAK_ratio_gt_2.5"
        rows.append({
            "case": f"remote_shaped_rows{row_count}_q4_0_x_q8_0",
            "rows": row_count,
            "hidden_n": n,
            "quant": "Q4_0xQ8_0",
            "C_best_T1": round(best_t1, 6),
            "C_best_T4": round(best_t4, 6),
            "ratio_T4_T1": round(ratio, 6),
            "winner_T1": winner_t1,
            "winner_T4": winner_t4,
            "speedup_vs_old_T4": round(old_t4 / best_t4, 6),
            "evidence_status": evidence_status,
            "conclusion": conclusion,
        })
    return rows


def run_robustness(verify_path, old_workingset_path, curve_summary_path, variant_timing_path, remote_rtile_dir=None):
    rows = []
    verify_rows = read_csv(verify_path)
    v_by_t = {int(r["T"]): r for r in verify_rows}
    summary = {r["metric"]: r["value"] for r in read_csv(curve_summary_path)}
    rows.append({
        "case": "current_rows512_q4_0_x_q8_0_best_curve",
        "rows": 512,
        "hidden_n": int(float(v_by_t[1].get("n", 11008))) if "n" in v_by_t[1] else 11008,
        "quant": "Q4_0xQ8_0",
        "C_best_T1": float(v_by_t[1]["C_verify_best_ms"]),
        "C_best_T4": float(v_by_t[4]["C_verify_best_ms"]),
        "ratio_T4_T1": round(float(v_by_t[4]["C_verify_best_ms"]) / float(v_by_t[1]["C_verify_best_ms"]), 6),
        "winner_T1": v_by_t[1]["winner_variant"],
        "winner_T4": v_by_t[4]["winner_variant"],
        "speedup_vs_old_T4": float(summary["speedup_vs_old_T4_x"]),
        "evidence_status": "measured_current_core_case",
        "conclusion": "SCOPED_GO_core_rows512_ratio_le_1.8",
    })

    old_rows = read_csv(old_workingset_path)
    grouped = defaultdict(dict)
    for r in old_rows:
        grouped[(int(r["rows"]), int(r["n"]))][int(r["T"])] = r
    for (row_count, n), by_t in sorted(grouped.items()):
        if 1 not in by_t or 4 not in by_t:
            continue
        ratio = float(by_t[4]["avg_ms"]) / float(by_t[1]["avg_ms"])
        rows_status = "old_curve_only"
        conclusion = "old_path_near_linear_working_set_reference"
        rows.append({
            "case": f"old_vecdot_rows{row_count}_q4_0_x_q8_0_workingset",
            "rows": row_count,
            "hidden_n": n,
            "quant": "Q4_0xQ8_0",
            "C_best_T1": float(by_t[1]["avg_ms"]),
            "C_best_T4": float(by_t[4]["avg_ms"]),
            "ratio_T4_T1": round(ratio, 6),
            "winner_T1": "old_vecdot_nrc1",
            "winner_T4": "old_vecdot_nrc1",
            "speedup_vs_old_T4": 1.0,
            "evidence_status": rows_status,
            "conclusion": conclusion,
        })

    variant_rows = read_csv(variant_timing_path)
    variants = defaultdict(dict)
    for r in variant_rows:
        variants[r["variant"]][int(r["T"])] = r
    for variant, by_t in sorted(variants.items()):
        if 1 not in by_t or 4 not in by_t or variant == "old_vecdot_nrc1":
            continue
        ratio = float(by_t[4]["avg_ms"]) / float(by_t[1]["avg_ms"])
        rows.append({
            "case": f"rows512_variant_{variant}",
            "rows": 512,
            "hidden_n": 11008,
            "quant": "Q4_0xQ8_0",
            "C_best_T1": float(by_t[1]["avg_ms"]),
            "C_best_T4": float(by_t[4]["avg_ms"]),
            "ratio_T4_T1": round(ratio, 6),
            "winner_T1": variant,
            "winner_T4": variant,
            "speedup_vs_old_T4": round(float(v_by_t[4]["C_verify_old_ms"]) / float(by_t[4]["avg_ms"]), 6),
            "evidence_status": "same_rows_variant_measurement",
            "conclusion": "supports_RTile_TTile_crossover" if ratio < 2.0 else "not_best_but_characterizes_variant",
        })
    rows.extend(shaped_working_set_rows(remote_rtile_dir))
    return rows


def run_final_decision(regime_rows, action_rows, selected_rows, comparison_rows, robustness_rows):
    mixed_selected = {r["policy"]: r for r in selected_rows if r["scope"] == "mixed"}
    comparison = {r["comparison_label"]: r for r in comparison_rows}
    regime_go = (
        any(r["policy_interpretation"] == "regime_shift_to_speculation" for r in regime_rows)
        and any(r["policy_interpretation"] == "low_acceptance_stays_no_spec" for r in regime_rows)
    )
    mixed_action = next(r for r in action_rows if r["scope"] == "mixed")
    multi_gain = float(mixed_action["multi_vs_two_oracle_gain_pct"])
    curve = comparison["best_curve_aware_selected"]
    goodput = comparison["best_goodput_only_selected"]
    curve_speedup = float(curve["speedup_vs_fixed_d3_pct"])
    curve_oracle = float(curve["oracle_reach"])
    curve_adv_goodput = float(curve["curve_aware_advantage_vs_goodput_pct"])
    robust_core = any(
        r["evidence_status"] == "measured_current_core_case" and float(r["ratio_T4_T1"]) <= 1.8
        for r in robustness_rows
    )
    robust_broad = any(
        r["evidence_status"] in {"larger_working_set_shaped", "cross_quant_shaped", "realistic_model_layer_shaped"}
        and float(r["ratio_T4_T1"]) <= 1.8
        for r in robustness_rows
    )

    selected_status = "NO-GO"
    if curve_speedup >= 8.0 and curve_oracle >= 0.90 and curve_adv_goodput >= 5.0:
        selected_status = "FULL GO"
    elif curve_speedup >= 5.0 or 0.85 <= curve_oracle < 0.90:
        selected_status = "CONDITIONAL"

    goodput_status = "CURVE-AWARE WINS" if curve_adv_goodput >= 5.0 else "TIE"
    if curve_adv_goodput <= -3.0:
        goodput_status = "GOODPUT WINS"

    robustness_status = "WEAK"
    if robust_core and robust_broad:
        robustness_status = "BROAD"
    elif robust_core:
        robustness_status = "SCOPED"
    larger_rows = [
        r for r in robustness_rows
        if r["evidence_status"] == "larger_working_set_shaped"
    ]
    if larger_rows:
        larger_evidence = "; ".join(
            f"rows{r['rows']}_ratio={float(r['ratio_T4_T1']):.3f}_{r['conclusion']}"
            for r in larger_rows
        )
    else:
        larger_evidence = "larger_working_set_shaped_not_measured"

    if selected_status == "FULL GO" and goodput_status == "CURVE-AWARE WINS" and robustness_status in {"BROAD", "SCOPED"}:
        final_version = "A. Strong system paper"
    elif regime_go and robustness_status in {"BROAD", "SCOPED"}:
        final_version = "B. Curve-shaping systems paper"
    else:
        final_version = "C. Kernel/measurement fallback"

    return [
        {
            "axis": "A. Curve-shaping beyond kernel speedup",
            "status": "GO" if regime_go else "CONDITIONAL",
            "evidence": "regime shift present and low-acceptance no-spec preserved" if regime_go else "regime shift incomplete",
            "interpretation": "new curve changes policy viability, not only kernel latency",
        },
        {
            "axis": "B. Two-action vs multi-point controller",
            "status": "MULTI-POINT" if multi_gain >= 5.0 else "TWO-ACTION",
            "evidence": f"multi_vs_two_oracle_gain_pct={multi_gain:.3f}; choices={mixed_action['multi_action_oracle_choices']}",
            "interpretation": "d=1/d=7 add little value; frame as curve-gated speculation" if multi_gain < 3.0 else "multi-point value is material",
        },
        {
            "axis": "C. Selected-only controller",
            "status": selected_status,
            "evidence": (
                f"best_curve={curve['policy']} speedup_vs_fixed_d3={curve_speedup:.3f}% "
                f"oracle_reach={curve_oracle:.3f}"
            ),
            "interpretation": "selected-only replay is useful but not full runtime GO unless oracle/overhead gates pass",
        },
        {
            "axis": "D. Goodput-only comparison",
            "status": goodput_status,
            "evidence": (
                f"curve_ms={curve['ms_per_token']} goodput_ms={goodput['ms_per_token']} "
                f"curve_advantage_vs_goodput={curve_adv_goodput:.3f}%"
            ),
            "interpretation": "controller novelty weak if selected-only goodput matches curve-aware",
        },
        {
            "axis": "E. Robustness across model/quant/working-set",
            "status": robustness_status,
            "evidence": f"core rows512 ratio <=1.8; {larger_evidence}; no cross-quant/real-layer shaped case yet" if robustness_status == "SCOPED" else "see robustness matrix",
            "interpretation": "scope paper to measured Q4_0xQ8_0 rows512 unless remote robustness is extended",
        },
        {
            "axis": "Final paper version",
            "status": final_version,
            "evidence": "derived from A-E gates",
            "interpretation": "recommended next action: fill robustness gaps and present controller as conditional unless goodput/runtime gates improve",
        },
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--position-complete", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--old-workingset", required=True)
    ap.add_argument("--curve-summary", required=True)
    ap.add_argument("--variant-timing", required=True)
    ap.add_argument("--remote-rtile-results")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    best_verify = load_verify(Path(args.verify), "best")
    old_verify = load_verify(Path(args.verify), "old")
    _combined, by_chunk = base.load_position_complete(Path(args.position_complete), best_verify)

    regime_rows = run_regime_shift(by_chunk, old_verify, best_verify)
    write_csv(out / "regime_shift_table.csv", regime_rows)

    action_rows = run_action_value(by_chunk, best_verify)
    write_csv(out / "d_action_value.csv", action_rows)

    selected_rows, selected_trace = run_selected_only(by_chunk, best_verify)
    write_csv(out / "selected_only_policy_summary.csv", selected_rows)
    write_csv(out / "selected_only_policy_trace.csv", selected_trace)

    goodput_rows = run_goodput_comparison(selected_rows)
    write_csv(out / "goodput_baseline_comparison.csv", goodput_rows)

    robustness_rows = run_robustness(
        Path(args.verify),
        Path(args.old_workingset),
        Path(args.curve_summary),
        Path(args.variant_timing),
        Path(args.remote_rtile_results) if args.remote_rtile_results else None,
    )
    write_csv(out / "curve_robustness_matrix.csv", robustness_rows)

    final_rows = run_final_decision(regime_rows, action_rows, selected_rows, goodput_rows, robustness_rows)
    write_csv(out / "final_decision_matrix.csv", final_rows)


if __name__ == "__main__":
    main()
