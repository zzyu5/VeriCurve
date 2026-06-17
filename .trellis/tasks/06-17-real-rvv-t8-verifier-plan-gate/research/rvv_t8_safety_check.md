# RVV T8 Safety Check

Date: 2026-06-17 Asia/Shanghai

Remote:

```text
ssh alias: rvv
hostname: ubuntu
kernel: Linux 6.12.23 riscv64
uptime: 14 days, 22:48
cores: 64
memory: 121 GiB total, 119 GiB available
load average: 0.11, 0.33, 0.28
active users: ubuntu pts/0, ubuntu pts/1
```

Process check:

```text
No active llama/cmake/ninja/gcc/g++/clang/make/TianchenRV/Codex heavy job was visible.
Only the transient ssh/bash/ps/grep processes from this safety check appeared.
```

Decision:

```text
SAFE_TO_PROCEED_WITH_LIMITS
```

Limits for this task:

```text
remote directory only: ~/vericurve-rv-lab/
no sudo
no package install
no TianchenRV tree mutation
nice -n 10 for compile/benchmark commands
timeout for remote commands
threads=1
build parallelism: -j1 only
```

Raw record:

```text
artifacts/rvv_t8_safety_check.txt
```
