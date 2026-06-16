#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path


TRACE_RE = re.compile(r"lookup_step_trace_(.+)_d(\d+)\.csv$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    artifacts = Path(args.artifacts)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    trace_rows = []
    summary_rows = []
    for path in sorted(artifacts.glob("lookup_step_trace_*_d*.csv")):
        m = TRACE_RE.match(path.name)
        if not m:
            continue
        workload = m.group(1)
        d = int(m.group(2))
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        total_drafted = 0
        total_accepted = 0
        full_accept = 0
        zero_accept = 0
        for row in rows:
            drafted = int(row["drafted_count"])
            accepted = int(row["accepted_count"])
            total_drafted += drafted
            total_accepted += accepted
            full_accept += int(drafted > 0 and accepted == drafted)
            zero_accept += int(drafted > 0 and accepted == 0)
            trace_rows.append({
                "workload": workload,
                "draft_source": "llama_lookup_stats_ngram",
                "d": d,
                "T": 1 + d,
                "chunk_id": row["chunk_id"],
                "step_id": row["step_id"],
                "drafted_count": drafted,
                "accepted_count": accepted,
                "pseudo_size_before": row["pseudo_size_before"],
                "pseudo_size_after": row["pseudo_size_after"],
                "trace_draft_update_us": row["trace_draft_update_us"],
                "method": "patched_llama_lookup_stats_per_step",
            })
        draft_steps = sum(1 for row in rows if int(row["drafted_count"]) > 0)
        summary_rows.append({
            "workload": workload,
            "d": d,
            "steps": len(rows),
            "draft_steps": draft_steps,
            "total_drafted": total_drafted,
            "total_accepted": total_accepted,
            "acceptance_per_draft_token": round(total_accepted / total_drafted, 6) if total_drafted else "",
            "mean_accept_per_step": round(total_accepted / len(rows), 6) if rows else "",
            "full_accept_step_rate": round(full_accept / draft_steps, 6) if draft_steps else "",
            "zero_accept_step_rate": round(zero_accept / draft_steps, 6) if draft_steps else "",
            "method": "patched_llama_lookup_stats_per_step_d3_only",
        })

    with (out / "online_controller_trace.csv").open("w", newline="") as f:
        fields = list(trace_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(trace_rows)

    with (out / "online_controller_trace_summary.csv").open("w", newline="") as f:
        fields = list(summary_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)


if __name__ == "__main__":
    main()
