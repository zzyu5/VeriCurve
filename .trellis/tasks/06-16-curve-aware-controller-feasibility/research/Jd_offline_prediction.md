# Offline J(d) Prediction

Artifacts:

```text
results/Jd_offline_prediction.csv
results/Jd_offline_summary.csv
scripts/offline_jd_controller.py
```

## Formula

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

Lower `J(d)` is better.

Candidate values:

```text
d in {0,1,3,7,15}
T = 1 + d
```

For `d=0`, there is no draft source and:

```text
J(0) = C_verify(1)
```

## Result Summary

Best old-curve choice:

```text
chat:       d=0, none, J=12.024 ms/token
code:       d=0, none, J=12.024 ms/token
rag:        d=0, none, J=12.024 ms/token
structured: d=0, none, J=12.024 ms/token
mixed:      d=0, none, J=12.024 ms/token
```

Best new-curve choice:

```text
chat:       d=0, none,       J=12.024 ms/token
code:       d=3, ngram-map,  J=5.436 ms/token
rag:        d=3, ngram-map,  J=8.092 ms/token
structured: d=3, ngram-map,  J=7.351 ms/token
mixed:      d=3, ngram-mod,  J=8.552 ms/token
```

Predicted speedup versus no speculation:

```text
chat:       1.000x
code:       2.212x
rag:        1.486x
structured: 1.636x
mixed:      1.406x
```

## Interpretation

The old curve does not make speculation profitable in this proxy. Its verifier
cost grows close enough to linearly that all workloads choose `d=0`.

The new row-blocked verifier curve changes the decision:

```text
low-acceptance chat remains at d=0
code/rag/structured move to d=3
mixed chooses d=3
```

This is exactly the controller opportunity pro3 asked for: the verifier curve
changes the optimal speculative budget, and the optimal budget is workload
dependent.

## Decision

```text
Status: GO for offline J(d) feasibility
```

The result supports continuing to a controller experiment. It does not yet prove
end-to-end online speedup because acceptance is a proxy and there is no runtime
EWMA controller integrated into llama.cpp.

## Caveats

`T=16` uses a composed verifier estimate, so any `d=15` conclusion is weaker
than the `d=3` conclusion.

The strongest positive signal is not `d=15`; it is that `d=3` becomes profitable
for high-acceptance workloads while `d=0` remains correct for low-acceptance
chat.
