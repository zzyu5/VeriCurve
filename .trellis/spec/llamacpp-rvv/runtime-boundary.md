# llama.cpp Runtime Boundary

VeriCurve-RV should first be integrated as a narrow measurement and decision layer, not as a broad llama.cpp rewrite.

## Allowed Early Touch Points

- Standalone profiler or microbenchmark harness.
- Low-bit matmul / vec-dot path tracing.
- Speculative decoding loop tracing for draft length, target verification T, and accepted token count.
- Profile loading and decision logging behind a compile-time or runtime flag.
- Minimal T-specialized verifier kernel wrappers after microbenchmark evidence exists.

## Avoid Early

- Rewriting ggml ABI before the verifier kernel shape is proven.
- Broad scheduler or graph runtime changes.
- Changes that affect non-RVV backends without a compatibility plan.
- Feature work that does not produce `C_verify(T)`, `C_draft(d)`, acceptance, or controller evidence.

## Integration Principle

The first controller patch should be conservative:

```text
profile cache + EWMA acceptance + choose_d() + log decisions + fallback to existing llama.cpp behavior
```

It should be easy to disable and should not silently change default llama.cpp behavior outside the experimental path.

