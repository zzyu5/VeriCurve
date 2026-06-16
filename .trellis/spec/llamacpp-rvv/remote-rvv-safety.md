# Shared `ssh rvv` Safety Protocol

The `rvv` machine is shared and has previously shown sensitivity under heavy multi-core compile or filesystem pressure. Remote work must be conservative.

## Before Any Remote Build or Benchmark

Run lightweight inspection first:

```bash
ssh rvv 'date; hostname; uname -a; uptime; who; nproc; free -h'
ssh rvv 'ps -eo pid,user,stat,pcpu,pmem,comm,args --sort=-pcpu | head -30'
```

Record the output in the task research log. If load is high, many users are active, or compiler/build processes are already consuming CPU, stop after read-only inspection.

## Remote Work Directory

Use an isolated directory, for example:

```text
~/vericurve-rv-lab/
```

Do not write inside TianchenRV working trees unless explicitly requested. Do not remove or mutate other users' files.

## Reusing Existing Remote llama.cpp Trees

Prefer task-owned paths under `~/vericurve-rv-lab/`. Reuse an existing remote
llama.cpp tree only when it avoids a larger build or download and the operation
is narrower than creating a fresh tree.

Allowed without extra approval:

```text
read-only inspection
binary --version / --help / --list-devices
CMakeCache.txt inspection
single-target build with -j1 when the tree is clearly not a control/canary run
tiny benchmark using an already-present model
```

Not allowed without explicit approval:

```text
git pull
clean rebuild
cmake reconfigure
deleting build outputs
editing source files
touching control/canary/instrumented trees
using a BLAS-enabled tree as RVV evidence
```

If an existing tree is used, record the path, selected target, backend flags,
and why alternatives were rejected in the task research log.

## Build Limits

- Default to `-j1`.
- Use `nice -n 10` for compile and benchmark commands.
- Use `timeout` for long commands.
- Avoid stress tests, high-concurrency builds, broad filesystem scans, and repeated clean rebuilds.
- Do not use `sudo`, package installation, system configuration changes, or kernel logs unless explicitly authorized.

## Benchmark Limits

- Start with source/path audit and tiny microbenchmarks.
- Record thread count explicitly.
- Prefer `--threads 1` first; only try more threads after the machine is idle and the user has reason to need it.
- Avoid long end-to-end model runs until a small profiler command works.

## Stop Conditions

Stop remote execution and report if:

- Load average is already high relative to available cores.
- Active TianchenRV/Codex/compile jobs are visible.
- Remote commands become slow, hang, or show filesystem/kernel errors.
- A build requires high parallelism or system packages.
- A command would need sudo or broad cleanup.
