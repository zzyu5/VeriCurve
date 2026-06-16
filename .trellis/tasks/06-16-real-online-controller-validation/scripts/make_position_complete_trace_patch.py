#!/usr/bin/env python3
import argparse
import difflib
from pathlib import Path


POSITION_OPEN = r'''    FILE * vc_position_complete = nullptr;
    const char * vc_position_complete_path = std::getenv("VERICURVE_LOOKUP_POSITION_COMPLETE_CSV");
    if (vc_position_complete_path && vc_position_complete_path[0]) {
        vc_position_complete = std::fopen(vc_position_complete_path, "w");
        if (!vc_position_complete) {
            LOG_ERR("failed to open VERICURVE_LOOKUP_POSITION_COMPLETE_CSV: %s\n", vc_position_complete_path);
            return 1;
        }
        std::fprintf(vc_position_complete,
                "chunk_id,position,candidate_d,drafted_count,accepted_count,target_available,pseudo_state_hash,recent_tokens_hash,context_hash,context_ngrams,context_edges,context_count_sum,draft_update_us\n");
    }

'''


POSITION_TRACE = r'''        if (vc_position_complete) {
            std::vector<llama_token> pc_pseudo;
            common_ngram_cache pc_context;
            pc_pseudo.push_back(inp_slice[0]);
            while ((int) pc_pseudo.size() < n_ctx) {
                const int pc_position = pc_pseudo.size();
                const vc_cache_stats pc_cache = vc_hash_ngram_cache(pc_context);
                const uint64_t pc_pseudo_hash = vc_hash_tokens(pc_pseudo, 0);
                const uint64_t pc_recent_hash = vc_hash_tokens(pc_pseudo, 16);
                const int candidate_ds[] = {0, 1, 3, 7};
                for (int candidate_d : candidate_ds) {
                    int candidate_drafted = 0;
                    int candidate_accept = 0;
                    uint64_t candidate_hash = 0;
                    const int64_t t_start_candidate_us = ggml_time_us();
                    vc_candidate_signature(pc_pseudo, inp_slice, candidate_d, pc_context, ngram_cache_dynamic, ngram_cache_static, candidate_drafted, candidate_accept, candidate_hash);
                    const int64_t candidate_us = ggml_time_us() - t_start_candidate_us;
                    std::fprintf(vc_position_complete,
                            "%d,%d,%d,%d,%d,%d,%016" PRIx64 ",%016" PRIx64 ",%016" PRIx64 ",%zu,%zu,%" PRId64 ",%" PRId64 "\n",
                            i_start / n_ctx,
                            pc_position,
                            candidate_d,
                            candidate_drafted,
                            candidate_accept,
                            n_ctx - pc_position,
                            pc_pseudo_hash,
                            pc_recent_hash,
                            pc_cache.hash,
                            pc_cache.ngrams,
                            pc_cache.edges,
                            pc_cache.count_sum,
                            candidate_us);
                }
                pc_pseudo.push_back(inp_slice[pc_pseudo.size()]);
                common_ngram_cache_update(pc_context, LLAMA_NGRAM_MIN, LLAMA_NGRAM_MAX, pc_pseudo, 1, false);
            }
        }

'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    orig_path = Path(args.orig)
    text = orig_path.read_text()
    updated = text

    updated = replace_once(
        updated,
        "    // Iterate over input tokens in chunks of size n_ctx.\n",
        POSITION_OPEN + "    // Iterate over input tokens in chunks of size n_ctx.\n",
        "position-open",
    )

    updated = replace_once(
        updated,
        "        int step_id = 0;\n",
        POSITION_TRACE + "        int step_id = 0;\n",
        "position-trace",
    )

    updated = replace_once(
        updated,
        "    if (vc_state_eq) {\n        std::fclose(vc_state_eq);\n    }\n\n    llama_backend_free();\n",
        "    if (vc_state_eq) {\n        std::fclose(vc_state_eq);\n    }\n"
        "    if (vc_position_complete) {\n        std::fclose(vc_position_complete);\n    }\n\n"
        "    llama_backend_free();\n",
        "position-close",
    )

    diff = difflib.unified_diff(
        text.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile="a/examples/lookup/lookup-stats.cpp",
        tofile="b/examples/lookup/lookup-stats.cpp",
    )
    Path(args.out).write_text("".join(diff))


if __name__ == "__main__":
    main()
