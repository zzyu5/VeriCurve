# pro2.md Guidance Summary

`doc/pro2.md` changes the research direction after the direct R1T4 failure.

## Main Correction

The failed direct kernel means the project cannot assume that making `T`
visible is enough. The next question is whether a materially different dataflow
can reduce total verifier cost for `T>1`.

## Required Branches

```text
A. curve-shaping microkernel viability:
   audit existing repack paths, then test RTile x TTile and layout packing.

B. schedule-variant runtime selection:
   look for real crossover between variants across T/B buckets.

C. cache-aware characterization:
   test whether model/quant/working-set changes explain the old near-linear
   curve and can support a measurement paper.

D. controller:
   forbidden until A4 GO/STRONG GO or B2 GO.
```

## Expected Final Decision

The task must recommend exactly one research direction:

```text
continue VeriCurve-RV system
pivot to Schedule-at-Inference-Time
pivot to cache/measurement paper
stop this line
```
