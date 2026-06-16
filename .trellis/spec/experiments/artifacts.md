# Experiment Artifacts

Use stable paths and preserve raw evidence.

## Directory Convention

```text
notes/                 human-readable source/path audits
scripts/               local or remote command wrappers
patches/               llama.cpp or profiler patches
artifacts/             raw logs, traces, command output
results/               parsed CSV/JSON
figures/               generated plots
```

## Required Metadata

Each experiment log should include:

- Date and timezone.
- Local or remote host.
- Source tree path.
- Git commit or archive identifier.
- Build command and flags.
- Model path or model identifier.
- Quantization format.
- Thread count.
- T/d candidate list.
- Warmup and measurement iterations.
- Raw command output path.
- Parsed result path.

When reusing an existing remote source tree instead of a task-owned checkout,
also record:

- exact remote path;
- why the tree was selected;
- whether alternative trees were rejected and why;
- git commit or binary-reported build commit;
- `CMakeCache.txt` facts for `GGML_RVV`, `GGML_BLAS`, `GGML_CPU`,
  `GGML_CPU_REPACK`, and `GGML_NATIVE` when present;
- target built or command run;
- whether the command modified only build outputs;
- confirmation that control/canary/instrumented trees were not mutated unless
  explicitly requested.

## File Naming

Prefer names that expose the experiment and source:

```text
results/C_old_verify_llamacpp-rvv_<commit>_threads1.csv
artifacts/rvv_preflight_<date>.txt
notes/current_llamacpp_rvv_path_<commit>.md
```

Do not overwrite older data without moving it aside or marking it invalid.

## Acceptable Early `C_old(T)` Result

For the first Go/No-Go pass, a Markdown record is acceptable if it includes the
raw remote JSON path and a parsed table with:

```text
T
avg_ns or avg_ms
total_ratio vs T=1
per_token_ms
per_token_ratio vs T=1
sample values or run count
```

The record must state whether the classification is behavioral timing only or
confirmed by call trace. Do not present a timing-only label as exact internal
kernel routing evidence.
