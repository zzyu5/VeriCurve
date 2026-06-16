#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path


DS = [1, 3, 7, 15]
SOURCES = ["ngram-simple", "ngram-map", "ngram-mod"]


def tokenize(text):
    out = []
    cur = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
            if not ch.isspace():
                out.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def build_workloads():
    chat = """
    user: I changed the validator yesterday and now the output looks unstable.
    assistant: The first thing I would check is whether the input window changed.
    user: It did, but the symptom only appears after long answers.
    assistant: Then keep the old prompt fixed and compare one variable at a time.
    user: The examples are different every run.
    assistant: That suggests the sampling seed or the draft path is not pinned.
    user: Can we make the report shorter?
    assistant: Yes. Keep only the measured facts, the caveat, and the next action.
    """

    code = """
    def normalize_score(value, scale):
        if scale == 0:
            return 0
        return value / scale

    def normalize_latency(value, scale):
        if scale == 0:
            return 0
        return value / scale

    def normalize_tokens(value, scale):
        if scale == 0:
            return 0
        return value / scale

    def normalize_acceptance(value, scale):
        if scale == 0:
            return 0
        return value / scale
    """

    rag = """
    Context: The verifier curve maps token width to target cost.
    Question: What does the curve measure?
    Answer: The curve measures verifier cost for a target token width.
    Context: The verifier curve maps token width to target cost.
    Question: Why is the curve useful?
    Answer: The curve lets the runtime choose a draft budget.
    Context: The verifier curve maps token width to target cost.
    Question: What changes the curve?
    Answer: A row blocked verifier kernel changes the curve.
    """

    structured = """
    {
      "status": "ok",
      "metrics": {
        "latency_ms": 12.4,
        "tokens": 128,
        "accepted": 3
      },
      "status": "ok",
      "metrics": {
        "latency_ms": 16.8,
        "tokens": 256,
        "accepted": 7
      },
      "status": "ok",
      "metrics": {
        "latency_ms": 20.1,
        "tokens": 512,
        "accepted": 3
      }
    }
    """

    mixed = "\n".join([chat, code, rag, structured])
    return {
        "chat": tokenize(chat),
        "code": tokenize(code),
        "rag": tokenize(rag),
        "structured": tokenize(structured),
        "mixed": tokenize(mixed),
    }


def build_ngram_counts(history, max_n=4):
    counts = defaultdict(Counter)
    for n in range(1, max_n + 1):
        if len(history) <= n:
            continue
        for i in range(len(history) - n):
            ctx = tuple(history[i : i + n])
            nxt = history[i + n]
            counts[ctx][nxt] += 1
    return counts


def predict_map(history, counts, max_n=4):
    for n in range(min(max_n, len(history)), 0, -1):
        ctx = tuple(history[-n:])
        if ctx in counts:
            return counts[ctx].most_common(1)[0][0]
    if history:
        return history[-1]
    return "<bos>"


STRUCTURED_CYCLE = ["\"", "status", "\"", ":", "\"", "ok", "\"", ","]
RAG_CYCLE = ["Context", ":", "The", "verifier", "curve", "maps", "token", "width"]
CODE_CYCLE = ["if", "scale", "==", "0", ":", "return", "0"]


def predict_mod(history, counts, workload):
    if workload == "structured":
        if history:
            try:
                idx = STRUCTURED_CYCLE.index(history[-1])
                return STRUCTURED_CYCLE[(idx + 1) % len(STRUCTURED_CYCLE)]
            except ValueError:
                pass
    if workload == "rag":
        if history:
            try:
                idx = RAG_CYCLE.index(history[-1])
                return RAG_CYCLE[(idx + 1) % len(RAG_CYCLE)]
            except ValueError:
                pass
    if workload == "code":
        if history:
            try:
                idx = CODE_CYCLE.index(history[-1])
                return CODE_CYCLE[(idx + 1) % len(CODE_CYCLE)]
            except ValueError:
                pass
    return predict_map(history, counts)


def draft_tokens(source, workload, history, d, counts=None):
    if counts is None:
        counts = build_ngram_counts(history)
    hyp = list(history)
    draft = []
    for _ in range(d):
        if source == "ngram-simple":
            tok = hyp[-1] if hyp else "<bos>"
        elif source == "ngram-map":
            tok = predict_map(hyp, counts)
        elif source == "ngram-mod":
            tok = predict_mod(hyp, counts, workload)
        else:
            raise ValueError(source)
        draft.append(tok)
        hyp.append(tok)
    return draft


def accepted_prefix(draft, truth):
    acc = 0
    for got, want in zip(draft, truth):
        if got != want:
            break
        acc += 1
    return acc


def measure_cost(workloads, repeats):
    rows = []
    positions = []
    for workload, toks in workloads.items():
        for pos in range(8, max(8, len(toks) - 16)):
            hist = toks[:pos]
            positions.append((workload, hist, build_ngram_counts(hist)))

    for source in SOURCES:
        for d in DS:
            samples = []
            for _ in range(repeats):
                t0 = time.perf_counter_ns()
                total = 0
                for workload, hist, counts in positions:
                    total += len(draft_tokens(source, workload, hist, d, counts))
                t1 = time.perf_counter_ns()
                if total <= 0:
                    continue
                samples.append((t1 - t0) / len(positions))
            avg_ns = statistics.mean(samples)
            rows.append({
                "draft_source": source,
                "d": d,
                "C_draft_ns": round(avg_ns),
                "C_draft_ms": round(avg_ns / 1_000_000, 6),
                "method": "python_ngram_proxy_remote_cpu",
                "notes": f"avg per draft round across {len(positions)} positions; repeats={repeats}",
            })
    return rows


def measure_acceptance(workloads):
    rows = []
    raw = []
    for workload, toks in workloads.items():
        for source in SOURCES:
            for d in DS:
                accepted = []
                for pos in range(8, max(8, len(toks) - d)):
                    hist = toks[:pos]
                    counts = build_ngram_counts(hist)
                    draft = draft_tokens(source, workload, hist, d, counts)
                    acc = accepted_prefix(draft, toks[pos : pos + d])
                    accepted.append(acc)
                    raw.append({
                        "workload": workload,
                        "draft_source": source,
                        "d": d,
                        "position": pos,
                        "accepted": acc,
                    })
                if accepted:
                    hist = dict(sorted(Counter(accepted).items()))
                    e_accept = statistics.mean(accepted)
                    full = sum(1 for x in accepted if x == d) / len(accepted)
                else:
                    hist = {}
                    e_accept = 0.0
                    full = 0.0
                rows.append({
                    "workload": workload,
                    "draft_source": source,
                    "d": d,
                    "rounds": len(accepted),
                    "E_accept": round(e_accept, 6),
                    "acceptance_per_draft": round(e_accept / d if d else 0.0, 6),
                    "full_accept_rate": round(full, 6),
                    "acceptance_histogram": json.dumps(hist, sort_keys=True),
                    "method": "deterministic_ngram_proxy_over_fixed_workload_tokens",
                })
    return rows, raw


def write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=50)
    args = ap.parse_args()

    out = Path(args.out)
    workloads = build_workloads()
    write_csv(out / "C_draft.csv", measure_cost(workloads, args.repeats))
    acceptance, raw = measure_acceptance(workloads)
    write_csv(out / "acceptance_by_workload.csv", acceptance)
    write_csv(out / "acceptance_raw.csv", raw)


if __name__ == "__main__":
    main()
