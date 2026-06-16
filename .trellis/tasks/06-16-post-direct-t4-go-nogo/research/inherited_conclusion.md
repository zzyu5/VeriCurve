# Inherited Conclusion From Direct R1T4

## Prior Evidence

The previous task, `06-16-minimal-t4-verifier-kernel`, established:

```text
current llama.cpp/RVV path:
  function: ggml_vec_dot_q4_0_q8_0
  nrc: 1
  C_old call-count ratios:
    T=1: 1.000
    T=2: 1.981
    T=4: 3.942
    T=8: 7.866

ggml-level old path:
  T=1: 6.416 ms, ratio 1.000
  T=2: 12.810 ms, ratio 1.997
  T=4: 25.620 ms, ratio 3.993
  T=8: 51.244 ms, ratio 7.987
  T=16: 102.580 ms, ratio 15.988

minimal direct R1T4 harness:
  correctness: pass, max_abs=0, max_rel=0
  old_t1: 11.738 ms
  old_t4: 46.890 ms = 3.995 x old_t1
  new_t4: 79.464 ms = 6.770 x old_t1 = 1.695 x old_t4
```

## Conclusion

The direct R1T4 microkernel is a No-Go for the current VeriCurve system path.
It exposes `T=4` but does not reshape the verifier cost curve.

The lesson is:

```text
T visible != curve shaping
```

The next valid kernel attempt must be materially different from direct R1T4.
Acceptable differences include:

```text
row blocking
token blocking
packed RHS layout
row-blocked or repacked weights
integration with existing llama.cpp repack/GEMV/GEMM machinery
another low-bit path with larger reusable work
```

Unacceptable continuations:

```text
four independent T1 calls hidden behind a T4 wrapper
minor rearrangements that still pay four independent reduction paths
controller or draft-budget work without a reshaped C_verify(T)
```

## Research State Entering This Task

The project remains alive only as a post-direct Go/No-Go tree:

```text
A. Can layout-aware RTile x TTile kernels bend C_verify(T)?
B. If not, does schedule-variant selection have real crossover?
C. If not, is there a cache/measurement paper?
D. If A/B/C fail, stop this line.
```
