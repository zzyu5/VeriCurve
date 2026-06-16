# pro.md Guidance Summary

Source:

```text
doc/pro.md
```

## Current State

The previous task has already crossed the first gate:

```text
old C(T) near-linear -> kernel gap exists
```

Measured prompt-pass ratios on `ssh rvv`:

```text
T=1  ratio=1.000
T=2  ratio=1.965
T=4  ratio=3.926
T=8  ratio=7.753
T=16 ratio=15.561
```

Correct state label:

```text
GO-kernel-gap
GO-minimal-T4-kernel
CONDITIONAL-controller
CONDITIONAL-full-system
```

## Main Reframing

Do not frame the project as a broad kernel-centered scheduler. The better
single-paper frame is:

```text
VeriCurve-RV: curve-shaping verifier kernels + curve-aware speculation
```

The causal chain is:

```text
microkernel design changes C_verify(T)
C_verify(T) changes speculation cost model
runtime policy chooses draft budget based on the changed curve
```

## Next Mandatory Gates

1. Trace the current llama.cpp/RVV path for T=1/2/4/8.
2. Build a ggml-level C_old(T) low-bit microbenchmark.
3. Implement the minimal T4 verifier microkernel only if the trace and
   microbenchmark leave a kernel gap.

Controller work must wait until after T4 changes the curve or the project is
explicitly downgraded.

## Safety Note

The previous 600-second build timeout was too short for a full fresh
`llama-bench` build at `-j1`. Future remote builds can use longer timeouts, but
should keep:

```text
nice -n 10
timeout
-j1 by default
no sudo
no package install
no TianchenRV working-tree writes
```

