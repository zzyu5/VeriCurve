#!/usr/bin/env python3
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


DS = [0, 1, 3, 7]
TWO_ACTION = [0, 3]


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        if not rows:
            raise ValueError(f"no rows to write for {path}")
        fields = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_verify(path):
    out = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            t = int(row["T"])
            out[t] = {
                "ms": float(row["C_verify_best_ms"]),
                "winner": row["winner_variant"],
            }
    return out


def row_cost(row, verify):
    d = int(row["candidate_d"])
    return verify[1 + d]["ms"] + float(row["trace_draft_us"]) / 1000.0


def row_tokens(row):
    return 1 + int(row["accepted_count"])


def choices_str(choices):
    if not choices:
        return ""
    return ";".join(f"d{d}={n}" for d, n in sorted(choices.items()))


def arms_str(arms):
    return ",".join(f"d{d}" for d in arms)


def load_steps(aligned_path, verify):
    by_key = defaultdict(dict)
    for row in read_csv(aligned_path):
        d = int(row["candidate_d"])
        key = (row["workload"], int(row["chunk_id"]), int(row["pseudo_position"]))
        out = dict(row)
        out["candidate_d"] = d
        out["T"] = 1 + d
        out["accepted_count"] = int(row["accepted_count"])
        out["drafted_count"] = int(row["drafted_count"])
        out["trace_draft_us"] = float(row["trace_draft_us"])
        out["step_cost_ms"] = row_cost(out, verify)
        out["emitted_tokens"] = row_tokens(out)
        by_key[key][d] = out

    steps = []
    incomplete = 0
    for key, candidates in by_key.items():
        if set(candidates.keys()) != set(DS):
            incomplete += 1
            continue
        workload, chunk_id, pseudo_position = key
        step_id = min(int(r["step_id"]) for r in candidates.values())
        steps.append({
            "key": key,
            "workload": workload,
            "chunk_id": chunk_id,
            "pseudo_position": pseudo_position,
            "step_id": step_id,
            "candidates": candidates,
        })
    steps.sort(key=lambda s: (s["workload"], s["chunk_id"], s["pseudo_position"]))
    return steps, incomplete


def split_steps(steps):
    by_chunk = defaultdict(list)
    for step in steps:
        by_chunk[(step["workload"], step["chunk_id"])].append(step)
    train = []
    test = []
    for key, chunk_steps in by_chunk.items():
        chunk_steps = sorted(chunk_steps, key=lambda s: s["pseudo_position"])
        cut = max(1, len(chunk_steps) // 2)
        train.extend(chunk_steps[:cut])
        test.extend(chunk_steps[cut:])
    return sorted(train, key=lambda s: (s["workload"], s["chunk_id"], s["pseudo_position"])), sorted(test, key=lambda s: (s["workload"], s["chunk_id"], s["pseudo_position"]))


class FixedPolicy:
    observability = "fixed"

    def __init__(self, d):
        self.d = d
        self.name = f"fixed_d{d}"
        self.policy_class = "fixed"
        self.params = f"d={d}"
        self.arms = [d]

    def select(self, step):
        return self.d, "fixed"

    def update(self, step, selected_d):
        pass


class WorkloadLabelPolicy:
    observability = "workload_label"

    def __init__(self):
        self.name = "workload_label_chat0_else3"
        self.policy_class = "workload_label_upper_bound"
        self.params = "chat/chat_low->d0;code/rag/structured->d3"
        self.arms = TWO_ACTION

    def select(self, step):
        if step["workload"] in {"chat", "chat_low"}:
            return 0, "workload_low_acceptance"
        return 3, "workload_high_acceptance"

    def update(self, step, selected_d):
        pass


class FullInfoEwmaPolicy:
    observability = "full_info"

    def __init__(self, verify, arms, alpha=0.3, margin=0.05, min_dwell=2):
        self.verify = verify
        self.arms = list(arms)
        self.alpha = alpha
        self.margin = margin
        self.min_dwell = min_dwell
        self.current_d = self.arms[0]
        self.dwell = min_dwell
        self.ewma = {d: 0.0 for d in self.arms}
        self.name = f"full_info_ewma_{arms_str(self.arms)}"
        self.policy_class = "full_info_ewma"
        self.params = f"alpha={alpha};margin={margin};min_dwell={min_dwell}"

    def select(self, step):
        scores = {}
        for d in self.arms:
            cand = step["candidates"][d]
            scores[d] = row_cost(cand, self.verify) / (1.0 + self.ewma[d])
        best_d = min(self.arms, key=lambda d: scores[d])
        reason = "hold"
        if best_d != self.current_d:
            if self.dwell >= self.min_dwell and scores[best_d] <= scores[self.current_d] * (1.0 - self.margin):
                self.current_d = best_d
                self.dwell = 0
                reason = "switch_margin"
            else:
                reason = "blocked_margin_or_dwell"
        return self.current_d, reason

    def update(self, step, selected_d):
        for d in self.arms:
            observed = int(step["candidates"][d]["accepted_count"])
            self.ewma[d] = (1.0 - self.alpha) * self.ewma[d] + self.alpha * observed
        self.dwell += 1


class SelectedThresholdPolicy:
    observability = "selected_only"

    def __init__(self, threshold, alpha=0.3, explore_period=16, min_d3_samples=4):
        self.threshold = threshold
        self.alpha = alpha
        self.explore_period = explore_period
        self.min_d3_samples = min_d3_samples
        self.ewma_d3 = 0.0
        self.d3_samples = 0
        self.steps = 0
        self.name = "selected_threshold_d3_vs_d0"
        self.policy_class = "selected_only_threshold"
        self.params = f"threshold={threshold};alpha={alpha};explore_period={explore_period};min_d3_samples={min_d3_samples}"
        self.arms = TWO_ACTION

    def select(self, step):
        self.steps += 1
        if self.d3_samples < self.min_d3_samples:
            return 3, "warmup_d3"
        if self.explore_period > 0 and self.steps % self.explore_period == 0:
            return 3, "periodic_d3_probe"
        if self.ewma_d3 >= self.threshold:
            return 3, "threshold_accept"
        return 0, "threshold_fallback_d0"

    def update(self, step, selected_d):
        if selected_d == 3:
            observed = int(step["candidates"][3]["accepted_count"])
            self.ewma_d3 = (1.0 - self.alpha) * self.ewma_d3 + self.alpha * observed
            self.d3_samples += 1


class SelectedEpsilonGreedyPolicy:
    observability = "selected_only"

    def __init__(self, verify, arms, epsilon=0.1, min_samples=2, min_dwell=1):
        self.verify = verify
        self.arms = list(arms)
        self.epsilon = epsilon
        self.min_samples = min_samples
        self.min_dwell = min_dwell
        self.counts = {d: 0 for d in self.arms}
        self.reward_sum = {d: 0.0 for d in self.arms}
        self.steps = 0
        self.current_d = self.arms[0]
        self.dwell = min_dwell
        self.name = f"selected_epsilon_greedy_{arms_str(self.arms)}"
        self.policy_class = "selected_only_epsilon_greedy"
        self.params = f"epsilon={epsilon};min_samples={min_samples};min_dwell={min_dwell}"

    def select(self, step):
        self.steps += 1
        for d in self.arms:
            if self.counts[d] < self.min_samples:
                self.current_d = d
                self.dwell = 0
                return d, "warmup_arm"
        period = int(round(1.0 / self.epsilon)) if self.epsilon > 0 else 0
        if period and self.steps % period == 0:
            idx = (self.steps // period) % len(self.arms)
            self.current_d = self.arms[idx]
            self.dwell = 0
            return self.current_d, "deterministic_explore"
        avg = {d: self.reward_sum[d] / self.counts[d] for d in self.arms}
        best_d = max(self.arms, key=lambda d: (avg[d], -d))
        if self.dwell >= self.min_dwell:
            self.current_d = best_d
            self.dwell = 0
            return self.current_d, "exploit_best_reward"
        return self.current_d, "min_dwell_hold"

    def update(self, step, selected_d):
        row = step["candidates"][selected_d]
        reward = row_tokens(row) / row_cost(row, self.verify)
        self.counts[selected_d] += 1
        self.reward_sum[selected_d] += reward
        self.dwell += 1


class SelectedUcbPolicy:
    observability = "selected_only"

    def __init__(self, verify, arms, c=0.1, min_samples=2, min_dwell=1):
        self.verify = verify
        self.arms = list(arms)
        self.c = c
        self.min_samples = min_samples
        self.min_dwell = min_dwell
        self.counts = {d: 0 for d in self.arms}
        self.reward_sum = {d: 0.0 for d in self.arms}
        self.steps = 0
        self.current_d = self.arms[0]
        self.dwell = min_dwell
        self.name = f"selected_ucb_{arms_str(self.arms)}"
        self.policy_class = "selected_only_ucb"
        self.params = f"c={c};min_samples={min_samples};min_dwell={min_dwell}"

    def select(self, step):
        self.steps += 1
        for d in self.arms:
            if self.counts[d] < self.min_samples:
                self.current_d = d
                self.dwell = 0
                return d, "warmup_arm"
        total = sum(self.counts.values())
        scores = {}
        for d in self.arms:
            mean = self.reward_sum[d] / self.counts[d]
            bonus = self.c * math.sqrt(math.log(max(total, 2)) / self.counts[d])
            scores[d] = mean + bonus
        best_d = max(self.arms, key=lambda d: (scores[d], -d))
        if self.dwell >= self.min_dwell:
            self.current_d = best_d
            self.dwell = 0
            return self.current_d, "ucb_best"
        return self.current_d, "min_dwell_hold"

    def update(self, step, selected_d):
        row = step["candidates"][selected_d]
        reward = row_tokens(row) / row_cost(row, self.verify)
        self.counts[selected_d] += 1
        self.reward_sum[selected_d] += reward
        self.dwell += 1


def replay_scan(steps, policy, verify):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    trace = []
    for ordinal, step in enumerate(steps):
        d, reason = policy.select(step)
        row = step["candidates"][d]
        c = row_cost(row, verify)
        t = row_tokens(row)
        total_cost += c
        total_tokens += t
        choices[d] += 1
        trace.append((step, d, reason, c, t))
        policy.update(step, d)
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens,
        "choices": dict(sorted(choices.items())),
        "steps_evaluated": len(trace),
        "trace": trace,
        "missing_transitions": 0,
        "terminal_transitions": 0,
        "chunks_started": len({(s["workload"], s["chunk_id"]) for s, *_ in trace}),
        "completed_chunks": len({(s["workload"], s["chunk_id"]) for s, *_ in trace}),
        "coverage_status": "recorded_position_scan_not_commit_aware",
    }


def replay_commit_available(steps, policy_factory, verify):
    by_chunk = defaultdict(dict)
    for step in steps:
        by_chunk[(step["workload"], step["chunk_id"])][step["pseudo_position"]] = step

    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    steps_evaluated = 0
    missing_transitions = 0
    terminal_transitions = 0
    completed_chunks = 0
    chunks_started = 0
    trace = []

    for key, pos_map in sorted(by_chunk.items()):
        chunks_started += 1
        policy = policy_factory()
        positions = sorted(pos_map)
        p = positions[0]
        max_p = positions[-1]
        while p in pos_map:
            step = pos_map[p]
            d, reason = policy.select(step)
            row = step["candidates"][d]
            c = row_cost(row, verify)
            t = row_tokens(row)
            total_cost += c
            total_tokens += t
            choices[d] += 1
            steps_evaluated += 1
            trace.append((step, d, reason, c, t))
            policy.update(step, d)
            next_p = p + t
            if next_p > max_p:
                terminal_transitions += 1
                completed_chunks += 1
                break
            if next_p not in pos_map:
                missing_transitions += 1
                break
            p = next_p

    status = "commit_aware_available_trace"
    if missing_transitions:
        status = "insufficient_trace_coverage_for_selected_path"
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens if total_tokens else float("nan"),
        "choices": dict(sorted(choices.items())),
        "steps_evaluated": steps_evaluated,
        "trace": trace,
        "missing_transitions": missing_transitions,
        "terminal_transitions": terminal_transitions,
        "chunks_started": chunks_started,
        "completed_chunks": completed_chunks,
        "coverage_status": status,
    }


def dinkelbach_scan_oracle(steps, verify):
    lam = min(verify[1 + d]["ms"] / (1 + d) for d in DS)
    chosen_trace = []
    for _ in range(100):
        total_cost = 0.0
        total_tokens = 0
        next_trace = []
        for step in steps:
            best = None
            for d in DS:
                row = step["candidates"][d]
                c = row_cost(row, verify)
                t = row_tokens(row)
                obj = c - lam * t
                if best is None or obj < best[0]:
                    best = (obj, d, c, t)
            _, d, c, t = best
            next_trace.append((step, d, "scan_dinkelbach", c, t))
            total_cost += c
            total_tokens += t
        new_lam = total_cost / total_tokens
        chosen_trace = next_trace
        if abs(new_lam - lam) < 1e-12:
            break
        lam = new_lam
    choices = defaultdict(int)
    for _, d, *_ in chosen_trace:
        choices[d] += 1
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens,
        "choices": dict(sorted(choices.items())),
        "steps_evaluated": len(chosen_trace),
        "trace": chosen_trace,
        "missing_transitions": 0,
        "terminal_transitions": 0,
        "chunks_started": len({(s["workload"], s["chunk_id"]) for s, *_ in chosen_trace}),
        "completed_chunks": len({(s["workload"], s["chunk_id"]) for s, *_ in chosen_trace}),
        "coverage_status": "recorded_position_scan_not_commit_aware",
    }


def transition_sanity_rows(steps):
    by_workload_chunk = defaultdict(dict)
    for step in steps:
        by_workload_chunk[(step["workload"], step["chunk_id"])][step["pseudo_position"]] = step

    rows = []
    for workload in sorted({s["workload"] for s in steps}):
        for d in DS:
            total = 0
            present = 0
            missing = 0
            terminal = 0
            emitted_min = None
            emitted_max = None
            for (w, chunk_id), pos_map in by_workload_chunk.items():
                if w != workload:
                    continue
                max_p = max(pos_map)
                for p, step in sorted(pos_map.items()):
                    emitted = row_tokens(step["candidates"][d])
                    emitted_min = emitted if emitted_min is None else min(emitted_min, emitted)
                    emitted_max = emitted if emitted_max is None else max(emitted_max, emitted)
                    next_p = p + emitted
                    if next_p > max_p:
                        terminal += 1
                    elif next_p in pos_map:
                        present += 1
                    else:
                        missing += 1
                    total += 1
            nonterminal = present + missing
            rows.append({
                "scope": workload,
                "candidate_d": d,
                "recorded_positions": total,
                "present_next_position": present,
                "missing_next_position": missing,
                "terminal_next_position": terminal,
                "present_fraction_nonterminal": round(present / nonterminal, 6) if nonterminal else "",
                "emitted_tokens_min": emitted_min,
                "emitted_tokens_max": emitted_max,
                "exact_commit_replay_supported": "yes" if missing == 0 else "no",
                "notes": "d=3 should be exact for the committed trace" if d == 3 else "non-d3 path needs position-complete trace when next positions are missing",
            })

    for d in DS:
        total = present = missing = terminal = 0
        emitted_min = None
        emitted_max = None
        for pos_map in by_workload_chunk.values():
            max_p = max(pos_map)
            for p, step in sorted(pos_map.items()):
                emitted = row_tokens(step["candidates"][d])
                emitted_min = emitted if emitted_min is None else min(emitted_min, emitted)
                emitted_max = emitted if emitted_max is None else max(emitted_max, emitted)
                next_p = p + emitted
                if next_p > max_p:
                    terminal += 1
                elif next_p in pos_map:
                    present += 1
                else:
                    missing += 1
                total += 1
        nonterminal = present + missing
        rows.append({
            "scope": "mixed",
            "candidate_d": d,
            "recorded_positions": total,
            "present_next_position": present,
            "missing_next_position": missing,
            "terminal_next_position": terminal,
            "present_fraction_nonterminal": round(present / nonterminal, 6) if nonterminal else "",
            "emitted_tokens_min": emitted_min,
            "emitted_tokens_max": emitted_max,
            "exact_commit_replay_supported": "yes" if missing == 0 else "no",
            "notes": "global transition coverage",
        })
    return rows


def make_policy_factories(verify):
    factories = []
    factories.append(("fixed_d0", lambda: FixedPolicy(0)))
    factories.append(("fixed_d1", lambda: FixedPolicy(1)))
    factories.append(("fixed_d3", lambda: FixedPolicy(3)))
    factories.append(("fixed_d7", lambda: FixedPolicy(7)))
    factories.append(("workload_label_chat0_else3", WorkloadLabelPolicy))
    factories.append(("full_info_ewma_d0_d3", lambda: FullInfoEwmaPolicy(verify, TWO_ACTION, alpha=0.3, margin=0.05, min_dwell=2)))
    factories.append(("full_info_ewma_d0_d1_d3_d7", lambda: FullInfoEwmaPolicy(verify, DS, alpha=0.3, margin=0.05, min_dwell=2)))
    for threshold in [0.4, 0.6, 0.8, 1.0, 1.25, 1.5]:
        factories.append((f"selected_threshold_t{threshold}", lambda threshold=threshold: SelectedThresholdPolicy(threshold=threshold, alpha=0.3, explore_period=16, min_d3_samples=4)))
    for epsilon in [0.05, 0.1, 0.2]:
        factories.append((f"selected_epsilon_d0_d3_e{epsilon}", lambda epsilon=epsilon: SelectedEpsilonGreedyPolicy(verify, TWO_ACTION, epsilon=epsilon, min_samples=2, min_dwell=1)))
    for c in [0.05, 0.1, 0.2, 0.5]:
        factories.append((f"selected_ucb_d0_d3_c{c}", lambda c=c: SelectedUcbPolicy(verify, TWO_ACTION, c=c, min_samples=2, min_dwell=1)))
    factories.append(("selected_epsilon_all_e0.1", lambda: SelectedEpsilonGreedyPolicy(verify, DS, epsilon=0.1, min_samples=2, min_dwell=1)))
    factories.append(("selected_ucb_all_c0.1", lambda: SelectedUcbPolicy(verify, DS, c=0.1, min_samples=2, min_dwell=1)))
    return factories


def summary_row(scope, mode, policy_key, policy, result, fixed_d3_ms, oracle_ms, notes=""):
    return {
        "scope": scope,
        "mode": mode,
        "policy": policy_key,
        "policy_class": getattr(policy, "policy_class", policy_key),
        "observability": getattr(policy, "observability", ""),
        "arms": arms_str(getattr(policy, "arms", [])),
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
        "coverage_status": result["coverage_status"],
        "parameters": getattr(policy, "params", ""),
        "notes": notes,
    }


def run_policy_table(steps, verify):
    scan_fixed = replay_scan(steps, FixedPolicy(3), verify)
    scan_oracle = dinkelbach_scan_oracle(steps, verify)
    rows = []
    factories = make_policy_factories(verify)

    rows.append(summary_row("mixed", "recorded_position_scan", "scan_oracle", FixedPolicy(0), scan_oracle, scan_fixed["ms_per_token"], scan_oracle["ms_per_token"], "scan oracle; not commit-aware"))
    for key, factory in factories:
        policy = factory()
        result = replay_scan(steps, policy, verify)
        rows.append(summary_row("mixed", "recorded_position_scan", key, policy, result, scan_fixed["ms_per_token"], scan_oracle["ms_per_token"], "old comparable mode; not selected-path correct"))

    commit_fixed = replay_commit_available(steps, lambda: FixedPolicy(3), verify)
    commit_oracle_ms = ""
    for key, factory in factories:
        policy_probe = factory()
        result = replay_commit_available(steps, factory, verify)
        rows.append(summary_row("mixed", "commit_aware_available_trace", key, policy_probe, result, commit_fixed["ms_per_token"], commit_oracle_ms, "exact only when missing_transitions=0"))
    return rows


def breakdown_rows(steps, verify):
    rows = []
    all_oracle = dinkelbach_scan_oracle(steps, verify)
    oracle_rate = all_oracle["ms_per_token"]
    ewma_policy = FullInfoEwmaPolicy(verify, DS, alpha=0.3, margin=0.05, min_dwell=2)
    ewma = replay_scan(steps, ewma_policy, verify)
    fixed_d3 = replay_scan(steps, FixedPolicy(3), verify)

    by_workload = defaultdict(list)
    for step in steps:
        by_workload[step["workload"]].append(step)

    def add_group(scope, category, key, policy_trace, oracle_trace, oracle_rate, notes):
        if not policy_trace:
            return
        p_cost = sum(x[3] for x in policy_trace)
        p_tokens = sum(x[4] for x in policy_trace)
        o_cost = sum(x[3] for x in oracle_trace)
        o_tokens = sum(x[4] for x in oracle_trace)
        p_choices = defaultdict(int)
        o_choices = defaultdict(int)
        for _, d, *_ in policy_trace:
            p_choices[d] += 1
        for _, d, *_ in oracle_trace:
            o_choices[d] += 1
        rows.append({
            "mode": "recorded_position_scan",
            "scope": scope,
            "category": category,
            "key": key,
            "steps": len(policy_trace),
            "policy_ms_per_token": round(p_cost / p_tokens, 6),
            "oracle_choice_ms_per_token": round(o_cost / o_tokens, 6),
            "oracle_rate_reference": round(oracle_rate, 6),
            "oracle_reach": round((o_cost / o_tokens) / (p_cost / p_tokens), 6),
            "policy_choices": choices_str(p_choices),
            "oracle_choices": choices_str(o_choices),
            "policy_total_cost_ms": round(p_cost, 6),
            "policy_total_tokens": p_tokens,
            "oracle_total_cost_ms": round(o_cost, 6),
            "oracle_total_tokens": o_tokens,
            "excess_cost_at_oracle_rate_ms": round((p_cost - oracle_rate * p_tokens) - (o_cost - oracle_rate * o_tokens), 6),
            "notes": notes,
        })

    ewma_by_key = {x[0]["key"]: x for x in ewma["trace"]}
    oracle_by_key = {x[0]["key"]: x for x in all_oracle["trace"]}
    fixed_by_key = {x[0]["key"]: x for x in fixed_d3["trace"]}

    for workload, subset in sorted(by_workload.items()):
        keys = [s["key"] for s in subset]
        wl_oracle = dinkelbach_scan_oracle(subset, verify)
        wl_oracle_by_key = {x[0]["key"]: x for x in wl_oracle["trace"]}
        add_group(workload, "workload_summary", workload, [ewma_by_key[k] for k in keys], [wl_oracle_by_key[k] for k in keys], wl_oracle["ms_per_token"], "full-info EWMA vs per-workload scan oracle")
        add_group(workload, "fixed_d3_summary", workload, [fixed_by_key[k] for k in keys], [wl_oracle_by_key[k] for k in keys], wl_oracle["ms_per_token"], "fixed d3 vs per-workload scan oracle")

    all_keys = [s["key"] for s in steps]
    add_group("mixed", "workload_summary", "mixed", [ewma_by_key[k] for k in all_keys], [oracle_by_key[k] for k in all_keys], oracle_rate, "full-info EWMA vs mixed scan oracle")
    add_group("mixed", "fixed_d3_summary", "mixed", [fixed_by_key[k] for k in all_keys], [oracle_by_key[k] for k in all_keys], oracle_rate, "fixed d3 vs mixed scan oracle")

    grouped = defaultdict(lambda: ([], []))
    hotspot = defaultdict(lambda: ([], []))
    for key in all_keys:
        p = ewma_by_key[key]
        o = oracle_by_key[key]
        grouped[f"d{p[1]}"][0].append(p)
        grouped[f"d{p[1]}"][1].append(o)
        if p[1] == 7:
            hotspot["choosing_d7"][0].append(p)
            hotspot["choosing_d7"][1].append(o)
        if p[1] == 0 and o[1] == 3:
            hotspot["staying_d0_when_oracle_d3"][0].append(p)
            hotspot["staying_d0_when_oracle_d3"][1].append(o)
        if p[1] == 0 and o[1] == 7:
            hotspot["staying_d0_when_oracle_d7"][0].append(p)
            hotspot["staying_d0_when_oracle_d7"][1].append(o)
        if p[1] != 3 and o[1] == 3:
            hotspot["missing_d3"][0].append(p)
            hotspot["missing_d3"][1].append(o)
        if p[1] == 3 and o[1] == 0:
            hotspot["choosing_d3_when_oracle_d0"][0].append(p)
            hotspot["choosing_d3_when_oracle_d0"][1].append(o)

    for key, (p_trace, o_trace) in sorted(grouped.items()):
        add_group("mixed", "regret_by_policy_d", key, p_trace, o_trace, oracle_rate, "EWMA chosen-d bucket")
    for key, (p_trace, o_trace) in sorted(hotspot.items()):
        add_group("mixed", "regret_hotspot", key, p_trace, o_trace, oracle_rate, "named mismatch bucket")

    return rows


def tune_train_test(steps, verify):
    train, test = split_steps(steps)
    train_fixed = replay_scan(train, FixedPolicy(3), verify)
    train_oracle = dinkelbach_scan_oracle(train, verify)
    test_fixed = replay_scan(test, FixedPolicy(3), verify)
    test_oracle = dinkelbach_scan_oracle(test, verify)

    candidates = []
    for threshold in [0.25, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 1.75, 2.0]:
        for alpha in [0.1, 0.2, 0.3, 0.5]:
            for explore_period in [8, 16, 32]:
                factory = lambda threshold=threshold, alpha=alpha, explore_period=explore_period: SelectedThresholdPolicy(threshold, alpha, explore_period, min_d3_samples=4)
                policy = factory()
                result = replay_scan(train, policy, verify)
                candidates.append((result["ms_per_token"], "selected_threshold", factory))
    for epsilon in [0.05, 0.1, 0.2, 0.3]:
        factory = lambda epsilon=epsilon: SelectedEpsilonGreedyPolicy(verify, TWO_ACTION, epsilon=epsilon, min_samples=2, min_dwell=1)
        policy = factory()
        result = replay_scan(train, policy, verify)
        candidates.append((result["ms_per_token"], "selected_epsilon", factory))
    for c in [0.01, 0.05, 0.1, 0.2, 0.5]:
        factory = lambda c=c: SelectedUcbPolicy(verify, TWO_ACTION, c=c, min_samples=2, min_dwell=1)
        policy = factory()
        result = replay_scan(train, policy, verify)
        candidates.append((result["ms_per_token"], "selected_ucb", factory))

    candidates.sort(key=lambda x: x[0])
    rows = []
    for rank, (_, family, factory) in enumerate(candidates[:10], start=1):
        train_policy = factory()
        train_result = replay_scan(train, train_policy, verify)
        test_policy = factory()
        test_result = replay_scan(test, test_policy, verify)
        rows.append({
            "rank_by_train": rank,
            "family": family,
            "policy": test_policy.name,
            "parameters": test_policy.params,
            "mode": "recorded_position_scan",
            "observability": test_policy.observability,
            "train_ms_per_token": round(train_result["ms_per_token"], 6),
            "train_relative_to_fixed_d3": round(train_result["ms_per_token"] / train_fixed["ms_per_token"], 6),
            "train_oracle_reach": round(train_oracle["ms_per_token"] / train_result["ms_per_token"], 6),
            "train_choices": choices_str(train_result["choices"]),
            "test_ms_per_token": round(test_result["ms_per_token"], 6),
            "test_relative_to_fixed_d3": round(test_result["ms_per_token"] / test_fixed["ms_per_token"], 6),
            "test_oracle_reach": round(test_oracle["ms_per_token"] / test_result["ms_per_token"], 6),
            "test_choices": choices_str(test_result["choices"]),
            "train_steps": train_result["steps_evaluated"],
            "test_steps": test_result["steps_evaluated"],
            "notes": "scan-mode tuning only; final selected-only proof needs position-complete or runtime trace",
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aligned", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    verify = load_verify(Path(args.verify))
    steps, incomplete = load_steps(Path(args.aligned), verify)
    out = Path(args.out)

    sanity = transition_sanity_rows(steps)
    sanity.append({
        "scope": "metadata",
        "candidate_d": "",
        "recorded_positions": len(steps),
        "present_next_position": "",
        "missing_next_position": "",
        "terminal_next_position": "",
        "present_fraction_nonterminal": "",
        "emitted_tokens_min": "",
        "emitted_tokens_max": "",
        "exact_commit_replay_supported": "no" if incomplete else "all_candidate_rows_complete",
        "notes": f"incomplete aligned step groups skipped={incomplete}",
    })
    write_csv(out / "replay_sanity_checks.csv", sanity)
    write_csv(out / "policy_family_replay.csv", run_policy_table(steps, verify))
    write_csv(out / "oracle_gap_breakdown.csv", breakdown_rows(steps, verify))
    write_csv(out / "policy_train_test.csv", tune_train_test(steps, verify))


if __name__ == "__main__":
    main()
