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
        fields = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_verify(path):
    verify = {}
    for row in read_csv(path):
        t = int(row["T"])
        verify[t] = {
            "ms": float(row["C_verify_best_ms"]),
            "winner": row["winner_variant"],
        }
    return verify


def load_position_complete(path, verify):
    by_chunk = defaultdict(dict)
    combined = []
    for row in read_csv(path):
        d = int(row["candidate_d"])
        workload = row["workload"]
        chunk_id = int(row["chunk_id"])
        position = int(row["position"])
        out = {
            "workload": workload,
            "chunk_id": chunk_id,
            "position": position,
            "candidate_d": d,
            "T": 1 + d,
            "drafted_count": int(row["drafted_count"]),
            "accepted_count": int(row["accepted_count"]),
            "target_available": int(row["target_available"]),
            "pseudo_state_hash": row["pseudo_state_hash"],
            "recent_tokens_hash": row["recent_tokens_hash"],
            "context_hash": row["context_hash"],
            "context_ngrams": int(row["context_ngrams"]),
            "context_edges": int(row["context_edges"]),
            "context_count_sum": int(row["context_count_sum"]),
            "draft_update_us": float(row["draft_update_us"]),
            "C_verify_best_ms": verify[1 + d]["ms"],
            "winner_variant": verify[1 + d]["winner"],
        }
        out["step_cost_ms"] = row_cost(out, verify)
        out["emitted_tokens"] = row_tokens(out)
        combined.append(out)
        by_chunk[(workload, chunk_id)].setdefault(position, {})[d] = out
    return combined, by_chunk


def row_cost(row, verify):
    return verify[1 + int(row["candidate_d"])]["ms"] + float(row["draft_update_us"]) / 1000.0


def row_tokens(row):
    return 1 + int(row["accepted_count"])


def choices_str(choices):
    return ";".join(f"d{d}={n}" for d, n in sorted(choices.items()))


class FixedPolicy:
    policy_class = "fixed"
    observability = "fixed"

    def __init__(self, d):
        self.d = d
        self.name = f"fixed_d{d}"
        self.params = f"d={d}"
        self.arms = [d]

    def select(self, candidates, workload):
        return self.d, "fixed"

    def update(self, chosen):
        pass


class WorkloadLabelPolicy:
    name = "workload_label_chat0_else3"
    policy_class = "workload_label_upper_bound"
    observability = "workload_label"
    params = "chat/chat_low->d0;code/rag/structured->d3"
    arms = TWO_ACTION

    def select(self, candidates, workload):
        return (0, "workload_low_acceptance") if workload in {"chat", "chat_low"} else (3, "workload_high_acceptance")

    def update(self, chosen):
        pass


class GoodputPolicy:
    name = "goodput_only"
    policy_class = "goodput_only"
    observability = "full_candidate_info"
    params = "choose max emitted tokens; tie high d"
    arms = DS

    def select(self, candidates, workload):
        d = max(DS, key=lambda x: (row_tokens(candidates[x]), x))
        return d, "max_emitted_tokens"

    def update(self, chosen):
        pass


class SelectedThresholdPolicy:
    policy_class = "selected_only_threshold"
    observability = "selected_only"
    arms = TWO_ACTION

    def __init__(self, threshold=0.4, alpha=0.3, probe_interval=8, min_samples=4):
        self.threshold = threshold
        self.alpha = alpha
        self.probe_interval = probe_interval
        self.min_samples = min_samples
        self.samples = 0
        self.ewma = 0.0
        self.steps = 0
        self.name = f"selected_threshold_t{threshold}_p{probe_interval}"
        self.params = f"threshold={threshold};alpha={alpha};probe_interval={probe_interval};min_samples={min_samples}"

    def select(self, candidates, workload):
        self.steps += 1
        if self.samples < self.min_samples:
            return 3, "warmup_d3"
        if self.probe_interval > 0 and self.steps % self.probe_interval == 0:
            return 3, "periodic_d3_probe"
        if self.ewma >= self.threshold:
            return 3, "threshold_accept"
        return 0, "threshold_fallback_d0"

    def update(self, chosen):
        if int(chosen["candidate_d"]) == 3:
            observed = int(chosen["accepted_count"])
            self.ewma = (1.0 - self.alpha) * self.ewma + self.alpha * observed
            self.samples += 1


def make_policy_factories():
    factories = [
        ("fixed_d0", lambda: FixedPolicy(0)),
        ("fixed_d1", lambda: FixedPolicy(1)),
        ("fixed_d3", lambda: FixedPolicy(3)),
        ("fixed_d7", lambda: FixedPolicy(7)),
        ("workload_label_chat0_else3", WorkloadLabelPolicy),
        ("goodput_only", GoodputPolicy),
    ]
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
        for probe in [8, 16]:
            factories.append((
                f"selected_threshold_t{threshold}_p{probe}",
                lambda threshold=threshold, probe=probe: SelectedThresholdPolicy(threshold=threshold, alpha=0.3, probe_interval=probe, min_samples=4),
            ))
    return factories


def replay_policy(by_chunk, policy_factory, verify, scope_filter=None, trace_rows=None):
    total_cost = 0.0
    total_tokens = 0
    choices = defaultdict(int)
    missing = 0
    terminal = 0
    steps = 0
    chunks = 0
    completed_chunks = 0
    for (workload, chunk_id), positions in sorted(by_chunk.items()):
        if scope_filter and workload not in scope_filter:
            continue
        chunks += 1
        policy = policy_factory()
        pos = min(positions)
        max_pos = max(positions)
        while pos in positions:
            candidates = positions[pos]
            if set(candidates) != set(DS):
                missing += 1
                break
            d, reason = policy.select(candidates, workload)
            chosen = candidates[d]
            cost = row_cost(chosen, verify)
            tokens = row_tokens(chosen)
            total_cost += cost
            total_tokens += tokens
            choices[d] += 1
            steps += 1
            if trace_rows is not None:
                trace_rows.append({
                    "workload": workload,
                    "chunk_id": chunk_id,
                    "position": pos,
                    "selected_d": d,
                    "accepted_count": chosen["accepted_count"],
                    "emitted_tokens": tokens,
                    "step_cost_ms": round(cost, 9),
                    "reason": reason,
                    "policy": policy.name,
                })
            policy.update(chosen)
            next_pos = pos + tokens
            if next_pos > max_pos:
                terminal += 1
                completed_chunks += 1
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
        "completed_chunks": completed_chunks,
    }


def oracle_for_chunk(positions, verify, lam):
    max_pos = max(positions)
    ordered = sorted(positions, reverse=True)
    dp = {max_pos + 1: 0.0}
    choice = {}
    for pos in ordered:
        best = None
        for d in DS:
            row = positions[pos][d]
            tokens = row_tokens(row)
            nxt = pos + tokens
            future_key = nxt if nxt <= max_pos else max_pos + 1
            if future_key not in dp:
                continue
            val = row_cost(row, verify) - lam * tokens + dp[future_key]
            if best is None or val < best[0]:
                best = (val, d, nxt)
        if best is not None:
            dp[pos] = best[0]
            choice[pos] = (best[1], best[2])
    return choice


def replay_oracle(by_chunk, verify, scope_filter=None):
    lam = min(verify[1 + d]["ms"] / (1 + d) for d in DS)
    final_choice_maps = {}
    for _ in range(100):
        total_cost = 0.0
        total_tokens = 0
        choice_maps = {}
        for key, positions in sorted(by_chunk.items()):
            workload, _chunk_id = key
            if scope_filter and workload not in scope_filter:
                continue
            cmap = oracle_for_chunk(positions, verify, lam)
            choice_maps[key] = cmap
            pos = min(positions)
            max_pos = max(positions)
            while pos in positions and pos in cmap:
                d, next_pos = cmap[pos]
                row = positions[pos][d]
                total_cost += row_cost(row, verify)
                total_tokens += row_tokens(row)
                if next_pos > max_pos:
                    break
                pos = next_pos
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
    for key, positions in sorted(by_chunk.items()):
        workload, _chunk_id = key
        if scope_filter and workload not in scope_filter:
            continue
        chunks += 1
        pos = min(positions)
        max_pos = max(positions)
        cmap = final_choice_maps[key]
        while pos in positions and pos in cmap:
            d, next_pos = cmap[pos]
            row = positions[pos][d]
            total_cost += row_cost(row, verify)
            total_tokens += row_tokens(row)
            choices[d] += 1
            steps += 1
            if next_pos > max_pos:
                break
            pos = next_pos
    return {
        "total_cost_ms": total_cost,
        "total_tokens": total_tokens,
        "ms_per_token": total_cost / total_tokens,
        "choices": dict(sorted(choices.items())),
        "missing_transitions": 0,
        "terminal_transitions": chunks,
        "steps_evaluated": steps,
        "chunks_started": chunks,
        "completed_chunks": chunks,
    }


def summary_row(scope, policy_key, policy, result, fixed_d3_ms, oracle_ms, notes=""):
    return {
        "scope": scope,
        "policy": policy_key,
        "policy_class": getattr(policy, "policy_class", policy_key),
        "observability": getattr(policy, "observability", ""),
        "arms": ",".join(f"d{d}" for d in getattr(policy, "arms", [])),
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
        "parameters": getattr(policy, "params", ""),
        "notes": notes,
    }


def run_summary(by_chunk, verify):
    rows = []
    trace = []
    fixed_d3 = replay_policy(by_chunk, lambda: FixedPolicy(3), verify)
    oracle = replay_oracle(by_chunk, verify)
    rows.append(summary_row("mixed", "oracle", FixedPolicy(0), oracle, fixed_d3["ms_per_token"], oracle["ms_per_token"], "commit-aware Dinkelbach path oracle"))
    for key, factory in make_policy_factories():
        trace_rows = trace if key.startswith("selected_threshold_t0.4_p8") else None
        policy_probe = factory()
        result = replay_policy(by_chunk, factory, verify, trace_rows=trace_rows)
        rows.append(summary_row("mixed", key, policy_probe, result, fixed_d3["ms_per_token"], oracle["ms_per_token"], "commit-aware replay"))

    # Best fixed mixed and per-workload aggregate.
    fixed_rows = [r for r in rows if r["policy"] in {"fixed_d0", "fixed_d1", "fixed_d3", "fixed_d7"}]
    best_fixed_mixed = min(fixed_rows, key=lambda r: float(r["ms_per_token"]))
    rows.append(dict(best_fixed_mixed, policy="best_fixed_mixed", policy_class="fixed_upper_bound", notes=f"same as {best_fixed_mixed['policy']}"))

    total_c = 0.0
    total_t = 0
    choices = defaultdict(int)
    for workload in sorted({k[0] for k in by_chunk}):
        scores = []
        for d in DS:
            res = replay_policy(by_chunk, lambda d=d: FixedPolicy(d), verify, scope_filter={workload})
            scores.append((res["ms_per_token"], d, res))
        _, d, res = min(scores, key=lambda x: x[0])
        total_c += res["total_cost_ms"]
        total_t += res["total_tokens"]
        choices[d] += res["steps_evaluated"]
    best_per_workload = {
        "total_cost_ms": total_c,
        "total_tokens": total_t,
        "ms_per_token": total_c / total_t,
        "choices": dict(sorted(choices.items())),
        "missing_transitions": 0,
        "terminal_transitions": len(by_chunk),
        "steps_evaluated": sum(choices.values()),
        "chunks_started": len(by_chunk),
        "completed_chunks": len(by_chunk),
    }
    rows.append(summary_row("mixed", "best_fixed_per_workload", FixedPolicy(0), best_per_workload, fixed_d3["ms_per_token"], oracle["ms_per_token"], "oracle workload label for fixed d"))

    workload_rows = []
    for workload in sorted({k[0] for k in by_chunk}):
        wd3 = replay_policy(by_chunk, lambda: FixedPolicy(3), verify, scope_filter={workload})
        woracle = replay_oracle(by_chunk, verify, scope_filter={workload})
        for key, factory in make_policy_factories():
            policy_probe = factory()
            res = replay_policy(by_chunk, factory, verify, scope_filter={workload})
            workload_rows.append(summary_row(workload, key, policy_probe, res, wd3["ms_per_token"], woracle["ms_per_token"], "commit-aware replay"))
        workload_rows.append(summary_row(workload, "oracle", FixedPolicy(0), woracle, wd3["ms_per_token"], woracle["ms_per_token"], "commit-aware per-workload oracle"))
    return rows, workload_rows, trace


def run_train_test(by_chunk, verify):
    # Split each chunk by position midpoint, preserving position-complete replay.
    train = defaultdict(dict)
    test = defaultdict(dict)
    for key, positions in by_chunk.items():
        ordered = sorted(positions)
        midpoint = ordered[len(ordered) // 2]
        for pos, cand in positions.items():
            (train if pos < midpoint else test)[key][pos] = cand
    train_fixed = replay_policy(train, lambda: FixedPolicy(3), verify)
    train_oracle = replay_oracle(train, verify)
    test_fixed = replay_policy(test, lambda: FixedPolicy(3), verify)
    test_oracle = replay_oracle(test, verify)

    candidates = []
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
        for alpha in [0.2, 0.3, 0.5]:
            for probe in [8, 16, 32]:
                factory = lambda threshold=threshold, alpha=alpha, probe=probe: SelectedThresholdPolicy(threshold=threshold, alpha=alpha, probe_interval=probe, min_samples=4)
                res = replay_policy(train, factory, verify)
                candidates.append((res["ms_per_token"], factory))
    candidates.sort(key=lambda x: x[0])
    rows = []
    for rank, (_, factory) in enumerate(candidates[:10], start=1):
        train_policy = factory()
        train_res = replay_policy(train, factory, verify)
        test_policy = factory()
        test_res = replay_policy(test, factory, verify)
        rows.append({
            "rank_by_train": rank,
            "policy": test_policy.name,
            "parameters": test_policy.params,
            "train_ms_per_token": round(train_res["ms_per_token"], 6),
            "train_relative_to_fixed_d3": round(train_res["ms_per_token"] / train_fixed["ms_per_token"], 6),
            "train_oracle_reach": round(train_oracle["ms_per_token"] / train_res["ms_per_token"], 6),
            "train_choices": choices_str(train_res["choices"]),
            "test_ms_per_token": round(test_res["ms_per_token"], 6),
            "test_relative_to_fixed_d3": round(test_res["ms_per_token"] / test_fixed["ms_per_token"], 6),
            "test_oracle_reach": round(test_oracle["ms_per_token"] / test_res["ms_per_token"], 6),
            "test_choices": choices_str(test_res["choices"]),
            "train_missing_transitions": train_res["missing_transitions"],
            "test_missing_transitions": test_res["missing_transitions"],
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--position-complete", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    verify = load_verify(Path(args.verify))
    combined, by_chunk = load_position_complete(Path(args.position_complete), verify)
    out = Path(args.out)
    write_csv(out / "position_complete_candidate_trace_scored.csv", combined)
    summary, by_workload, trace = run_summary(by_chunk, verify)
    write_csv(out / "commit_aware_replay_summary.csv", summary)
    write_csv(out / "commit_aware_replay_by_workload.csv", by_workload)
    write_csv(out / "commit_aware_selected_threshold_trace.csv", trace)
    write_csv(out / "commit_aware_train_test.csv", run_train_test(by_chunk, verify))


if __name__ == "__main__":
    main()
