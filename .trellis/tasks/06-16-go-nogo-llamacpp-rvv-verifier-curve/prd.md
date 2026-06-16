# Go/No-Go: llama.cpp RVV verifier curve reconnaissance

## Objective

Decide whether VeriCurve-RV is initially viable by safely auditing current llama.cpp/RVV verifier behavior and, only if the shared `rvv` machine is quiet enough, running bounded llama.cpp reconnaissance without interfering with TianchenRV or other users.

## Research Question

Can we observe enough evidence that `C_verify(T)` on RISC-V/RVV is a meaningful curve for speculative decoding decisions?

The first task does not need to finish the full paper system. It must establish whether the direction is:

- `GO-strong`
- `GO-characterization`
- `CONDITIONAL`
- `NO-GO`
- or `INSUFFICIENT-EVIDENCE` when remote conditions prevent safe measurement.

## Sources of Truth

- `.trellis/spec/project/positioning.md`
- `.trellis/spec/project/scope.md`
- `.trellis/spec/llamacpp-rvv/current-path-audit.md`
- `.trellis/spec/llamacpp-rvv/remote-rvv-safety.md`
- `.trellis/spec/experiments/go-nogo.md`
- `.trellis/spec/experiments/artifacts.md`
- `.trellis/tasks/06-16-go-nogo-llamacpp-rvv-verifier-curve/research/design-source-summary.md`

## Scope

### In Scope

1. Inspect local or upstream llama.cpp source to identify RVV low-bit paths and speculative decoding path.
2. Probe `ssh rvv` with read-only, lightweight commands.
3. Reuse an existing remote llama.cpp tree if present and safe.
4. Clone or update a shallow llama.cpp copy only under `~/vericurve-rv-lab/` if remote load is low.
5. Run at most low-priority, single-job build or tiny probe commands during this turn.
6. Persist commands and evidence in this task's `research/` directory.

### Out of Scope

1. Full T-specialized kernel implementation.
2. Full end-to-end llama.cpp benchmark campaign.
3. Package installation or sudo on `rvv`.
4. Any operation inside TianchenRV working trees.
5. High-parallelism compile or stress test.
6. Claims of final performance speedup.

## Remote Safety Requirements

Before remote build or benchmark:

```bash
ssh rvv 'date; hostname; uname -a; uptime; who; nproc; free -h'
ssh rvv 'ps -eo pid,user,stat,pcpu,pmem,comm,args --sort=-pcpu | head -30'
```

Stop after read-only inspection if:

- load is high relative to available cores;
- active TianchenRV, Codex, compiler, or benchmark jobs are visible;
- the remote is slow or unstable;
- build requires high parallelism, sudo, or package installation.

If continuing:

- use `~/vericurve-rv-lab/`;
- use `nice -n 10`;
- use `timeout`;
- default to `-j1`;
- record every command and output path.

## Work Plan

### Phase A: Local llama.cpp reconnaissance

- Check whether `/home/kingdom/phdworks/llama.cpp` exists.
- Record git commit and local dirty state if it exists.
- Search for RVV, RISC-V, low-bit vec-dot/mul-mat, and speculative decoding source paths.
- Produce `research/local_llamacpp_path_audit.md`.

### Phase B: Remote preflight

- Run read-only `ssh rvv` preflight commands.
- Record system/load/process facts in `research/rvv_preflight.md`.
- Decide whether remote build/test can proceed safely.

### Phase C: Bounded remote llama.cpp check

Only if Phase B is safe:

- inspect existing remote llama.cpp or create `~/vericurve-rv-lab/`;
- avoid modifying TianchenRV or other project trees;
- run source inspection and, if cheap, a single-job build/probe;
- record output in `research/remote_llamacpp_recon.md`.

### Phase D: Preliminary Go/No-Go classification

Write `research/go_nogo_preliminary.md` with:

- current path classification: `multi_rhs_present`, `generic_batch_path`, `repeated_t1`, or `unresolved`;
- remote feasibility;
- whether the next task should be C_old(T) profiling, minimal T4 microkernel, or fallback characterization.

## Acceptance Criteria

- Trellis has project-specific spec layers and this task is current.
- Local or upstream llama.cpp source audit is recorded.
- `ssh rvv` preflight is recorded, or a concrete connection failure is recorded.
- No high-risk remote operation is performed.
- A preliminary Go/No-Go label is written with evidence and caveats.

