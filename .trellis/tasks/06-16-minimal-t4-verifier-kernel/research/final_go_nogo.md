# Final Go/No-Go for Minimal T4 Gate

## Final Label

```text
NO-GO for current minimal direct-vecdot T4 VeriCurve system path
```

More precise status:

```text
GO-characterization: yes
GO-kernel-gap: yes
GO-minimal-direct-T4: no
GO-controller: no
FULL SYSTEM GO: no
```

## Evidence Chain

1. Previous prompt-pass result showed near-linear model-level old curve:

```text
T=4 ratio ~= 3.93
T=8 ratio ~= 7.75
```

2. Fresh upstream traced build confirmed current path:

```text
ggml_vec_dot_q4_0_q8_0
nrc = 1
call_count ratio T=1/2/4/8 ~= 1.00/1.98/3.94/7.87
```

3. ggml-level old-path microbenchmark confirmed low-level linearity:

```text
C_old_qmatmul(4) = 3.993 * C_old_qmatmul(1)
```

4. Minimal direct T4 kernel passed correctness but failed performance:

```text
C_new(4) = 6.770 * C_old(1)
C_new(4) = 1.695 * C_old(4)
max_abs = 0
max_rel = 0
```

## Consequence

Per `doc/pro.md` and `.trellis/spec/curve-system/kernel-design.md`, the
controller path should not proceed after this result. The physical curve was
not reshaped by the minimal T4 kernel; therefore a curve-aware controller would
not have a validated new verifier curve to exploit.

## What Remains Viable

The characterization result remains valuable:

```text
current llama.cpp/RVV Q4_0 path is repeated-T1-like
```

The system idea is not supported under the minimal direct T4 design. A future
task may reopen the kernel question only by changing the kernel family, such as
using an interleaved/repacked layout or another quant path. That would be a new
kernel research task, not controller continuation.

