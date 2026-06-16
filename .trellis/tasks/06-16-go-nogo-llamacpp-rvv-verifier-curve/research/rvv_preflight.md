# `ssh rvv` Preflight

## Commands

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 rvv 'date; hostname; uname -a; uptime; who; nproc; free -h'
ssh -o BatchMode=yes -o ConnectTimeout=10 rvv 'ps -eo pid,user,stat,pcpu,pmem,comm,args --sort=-pcpu | head -30'
ssh -o BatchMode=yes -o ConnectTimeout=10 rvv 'pgrep -af "cmake|ninja|make|clang|gcc|g\+\+|cc1|llama|codex|TianChen|Tianchen|python" || true'
```

## Host Snapshot

```text
date: Mon Jun 15 16:34:12 UTC 2026
hostname: ubuntu
kernel: Linux ubuntu 6.12.23 #1 SMP Thu Apr 17 11:46:50 EDT 2025 riscv64
uptime: up 13 days, 13:24
users: 3
load average: 0.00, 0.00, 0.01
CPUs: 64
memory: 121Gi total, 2.2Gi used, 92Gi free, 119Gi available
swap: 0B
```

Top process table did not show active user compile or benchmark load. The high `%CPU` line was the short-lived `ps` command itself. Targeted process search found only the current shell and unattended-upgrades wait process:

```text
2398 /usr/bin/python3 /usr/share/unattended-upgrades/unattended-upgrade-shutdown --wait-for-signal
```

## Hardware Facts

```text
Architecture: riscv64
CPU(s): 64
NUMA node(s): 1
ISA: rv64imafdcv_zicbom_zicboz_zicntr_zicond_zicsr_zifencei_zihintntl_zihintpause_zihpm_zawrs_zfa_zfh_zfhmin_...
```

`lscpu` did not report VLEN. Runtime VLEN still needs to be captured by a small program or llama.cpp feature print.

## Safety Decision

Remote state was safe enough for:

- shallow clone under `~/vericurve-rv-lab/`;
- CMake configure;
- single-job, low-priority partial build.

Remote state did not justify:

- high-parallelism build;
- long benchmark campaign;
- model download or end-to-end run;
- any operation in TianchenRV directories.

## Final Residual Process Check

After the build timeout:

```text
uptime: load average 0.85, 0.90, 0.54
pgrep compile/llama patterns: no residual compile or llama process beyond the current pgrep shell
```

After the later bounded `llama-bench` run:

```text
date: Mon Jun 15 17:16:00 UTC 2026
uptime: load average 0.08, 0.22, 0.45
pgrep compile/llama patterns: no residual compile or llama process beyond the current pgrep shell
```
