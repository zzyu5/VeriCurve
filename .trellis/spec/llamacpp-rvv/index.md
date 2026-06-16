# llama.cpp/RVV Spec

## Pre-Development Checklist

- Confirm the llama.cpp source tree or upstream commit being inspected.
- Record whether evidence comes from local source, upstream clone, or remote `rvv`.
- Before remote commands, read [remote-rvv-safety](./remote-rvv-safety.md).
- For path claims, preserve exact file names, function names, build flags, and command output.

## Guidelines

| Guide | Description |
|---|---|
| [runtime-boundary](./runtime-boundary.md) | Where VeriCurve-RV may touch llama.cpp and where it should not. |
| [current-path-audit](./current-path-audit.md) | How to audit current RVV verifier behavior. |
| [remote-rvv-safety](./remote-rvv-safety.md) | Safe protocol for shared `ssh rvv` work. |

## Quality Check

- No remote benchmark result is valid without remote date, host identity, build command, thread count, and load context.
- No path audit is valid unless it states whether T>1 is multi-RHS, repeated T1, batch matmul, or unresolved.
- No build should use high parallelism on `rvv` by default.

