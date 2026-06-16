# rvv Safety Check

Timestamp:

```text
Tue Jun 16 04:58:04 UTC 2026
```

Host:

```text
hostname: ubuntu
kernel: Linux ubuntu 6.12.23 #1 SMP Thu Apr 17 11:46:50 EDT 2025 riscv64
nproc: 64
```

Load and memory:

```text
uptime: 04:58:04 up 14 days, 1:48, 9 users, load average: 0.51, 0.21, 0.11
memory: 121 GiB total, 2.2 GiB used, 92 GiB free, 119 GiB available
swap: 0 B
```

Logged-in sessions:

```text
ubuntu pts/0 2026-06-15 07:56 (192.168.102.64)
ubuntu pts/1 2026-06-14 14:14 (192.168.102.64)
```

Relevant process probes:

```text
pgrep -af TianchenRV: no matches
pgrep -af cmake: no matches
pgrep -af ninja: no matches
pgrep -af llama: no matches
pgrep -af gemv_probe: 2881408 ./gemv_probe_il 4096 8 20000 30
```

Decision:

```text
Safe for read-only source audit and low-priority single-process microbenchmarks.
Do not run multicore builds or long model-level sweeps while gemv_probe_il is active.
Use isolated paths under ~/vericurve-rv-lab/.
```
