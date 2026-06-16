#!/usr/bin/env python3
import argparse
import csv
import math
import re
from pathlib import Path


WORKLOADS = ["chat_low", "chat", "code", "rag", "structured"]
DS = [1, 3, 7]


PATTERNS = {
    "n_draft": re.compile(r"n_draft\s+=\s+(\d+)"),
    "n_predict": re.compile(r"n_predict\s+=\s+(\d+)"),
    "n_drafted": re.compile(r"n_drafted\s+=\s+(\d+)"),
    "t_draft": re.compile(r"t_draft\s+=\s+([0-9.]+) ms,\s+([0-9.]+|nan|inf) us per token"),
    "n_accept": re.compile(r"n_accept\s+=\s+(\d+)"),
    "accept": re.compile(r"accept\s+=\s+([0-9.]+|nan)%"),
}


def read_status(path):
    if not path.exists():
        return "missing"
    text = path.read_text().strip()
    return text.split("=", 1)[1] if "=" in text else text


def parse_file(path):
    text = path.read_text(errors="replace")
    out = {}
    for key, pat in PATTERNS.items():
        matches = pat.findall(text)
        if not matches:
            continue
        val = matches[-1]
        if key == "t_draft":
            out["t_draft_ms"] = float(val[0])
            out["draft_us_per_token"] = float(val[1]) if val[1] not in {"nan", "inf"} else math.nan
        elif key == "accept":
            out["accept_percent"] = float(val) if val != "nan" else math.nan
        else:
            out[key] = int(val)
    return out


def load_verify(path):
    table = {}
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            table[int(row["T"])] = {
                "C_verify_best_ms": float(row["C_verify_best_ms"]),
                "winner_variant": row["winner_variant"],
            }
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--verify", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    artifacts = Path(args.artifacts)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    verify = load_verify(Path(args.verify))

    rows = []
    j_rows = []
    for workload in WORKLOADS:
        for d in DS:
            stem = f"lookup_stats_{workload}_d{d}"
            parsed = parse_file(artifacts / f"{stem}.stderr")
            status = read_status(artifacts / f"{stem}.status")
            n_drafted = parsed.get("n_drafted", 0)
            n_accept = parsed.get("n_accept", 0)
            accept_per_draft = (n_accept / n_drafted) if n_drafted else math.nan
            rounds_est = (n_drafted / d) if d and n_drafted else math.nan
            e_accept_est = (n_accept / rounds_est) if rounds_est and not math.isnan(rounds_est) else math.nan
            c_draft_ms = parsed.get("t_draft_ms", math.nan)
            c_draft_per_round_ms = (c_draft_ms / rounds_est) if rounds_est and not math.isnan(rounds_est) else math.nan
            row = {
                "workload": workload,
                "draft_source": "llama_lookup_stats_ngram",
                "d": d,
                "requested_T": 1 + d,
                "status": status,
                "n_predict": parsed.get("n_predict", 0),
                "n_drafted": n_drafted,
                "n_accept": n_accept,
                "acceptance_per_draft_token": round(accept_per_draft, 6) if not math.isnan(accept_per_draft) else "",
                "rounds_est": round(rounds_est, 6) if not math.isnan(rounds_est) else "",
                "E_accept_est": round(e_accept_est, 6) if not math.isnan(e_accept_est) else "",
                "t_draft_total_ms": c_draft_ms if not math.isnan(c_draft_ms) else "",
                "C_draft_est_per_round_ms": round(c_draft_per_round_ms, 9) if not math.isnan(c_draft_per_round_ms) else "",
                "method": "llama_lookup_stats_controlled_aggregate",
                "notes": "aggregate-only; rounds_est assumes each draft round requested d tokens",
            }
            rows.append(row)

            T = 1 + d
            if T in verify and not math.isnan(e_accept_est):
                c_verify = verify[T]["C_verify_best_ms"]
                c_draft_round = c_draft_per_round_ms if not math.isnan(c_draft_per_round_ms) else 0.0
                j = (c_verify + c_draft_round) / (1.0 + e_accept_est)
                j_rows.append({
                    "workload": workload,
                    "d": d,
                    "T": T,
                    "C_verify_best_ms": c_verify,
                    "winner_variant": verify[T]["winner_variant"],
                    "E_accept_est": round(e_accept_est, 6),
                    "C_draft_est_per_round_ms": round(c_draft_round, 9),
                    "J_est_ms_per_token": round(j, 6),
                    "method": "aggregate_lookup_stats_estimate",
                })

    with (out / "real_acceptance_trace.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with (out / "controlled_lookup_Jd_estimate.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(j_rows[0].keys()))
        writer.writeheader()
        writer.writerows(j_rows)


if __name__ == "__main__":
    main()
