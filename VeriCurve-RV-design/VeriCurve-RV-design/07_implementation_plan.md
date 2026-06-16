# 07. 实现路线图

## 1. 原则

单篇论文要控制范围：

```text
做：
  llama.cpp/RVV + characterization + minimal kernels + controller

暂不做：
  full TianchenRV integration
  agent-based optimization
  multi-framework runtime
  complex tree speculative decoding
  formal verification
```

---

## 2. Phase 0: 准备与代码阅读

目标：确认 llama.cpp/RVV current path。

任务：

```text
1. Build llama.cpp on RVV board
2. Enable RVV flags
3. Identify q4/q8 mul_mat / vec_dot path
4. Identify speculative decoding path
5. Add basic tracing macros
```

产出：

```text
notes/current_llamacpp_rvv_path.md
scripts/build_llamacpp_rvv.sh
patches/trace_kernel_calls.diff
```

时间：3-5 天。

---

## 3. Phase 1: Curve Profiler

目标：先拿到 C_old(T)。

任务：

```text
1. 写 verifier microbenchmark harness
2. 支持 T=1,2,4,8,16
3. 支持 Q4_0/Q4_K_M/Q8 至少一种
4. 输出 CSV/JSON
5. 用 perf/stat 收集 counters
```

命令示例：

```bash
./vericurve-profiler \
  --model model.gguf \
  --quant Q4_K_M \
  --T 1,2,4,8,16 \
  --threads 1,4 \
  --out results/C_old.csv
```

产出：

```text
src/vericurve_profiler.cpp
results/C_old_*.csv
analysis/plot_curves.py
```

Go/No-Go：

```text
如果 C_old(4) < 2C_old(1)，当前路径已经不错，需要调整论文重点。
如果 C_old(4) ≈ 4C_old(1)，进入 Phase 2。
```

---

## 4. Phase 2: Minimal T-specialized kernel

目标：证明 curve can be reshaped。

任务：

```text
1. 先选一个 low-bit path：Q4_0 × Q8_0 或最容易接的 Q4_K_M
2. 写 T1/T4 microkernel
3. 对比 old path
4. 再扩展 T2/T8
```

实现策略：

```text
优先手写 RVV intrinsics，降低对 TianchenRV 的依赖。
如果 TianchenRV 已经能快速生成，则可以使用，但论文中不强绑定。
```

产出：

```text
src/rvv_verify_t1.c
src/rvv_verify_t4.c
src/rvv_verify_t8.c
results/C_new_*.csv
```

Go/No-Go：

```text
如果 C_new(4)/C_new(1) <= 2.5，继续。
如果 <= 2.0，非常理想。
如果仍 > 3.5，暂停方向。
```

---

## 5. Phase 3: Draft Cost and Acceptance Profiler

目标：测 C_draft(d) 和 acceptance drift。

任务：

```text
1. 接 llama.cpp ngram draft
2. 如果可行，接 small draft model
3. 记录 d=1,3,7,15 的 draft cost
4. 记录 accepted tokens
5. 跑 chat/code/RAG/structured/mixed workload
```

产出：

```text
results/C_draft_ngram.csv
results/C_draft_model.csv
results/acceptance_by_workload.csv
```

---

## 6. Phase 4: Curve-aware Controller

目标：实现简单 controller。

任务：

```text
1. 加 profile loader
2. 加 EWMA acceptance estimator
3. 实现 choose_d()
4. 集成到 llama.cpp speculative loop
5. 加日志
```

伪代码：

```c
int vc_choose_d(const vc_profile *p, const vc_stats *s) {
    int candidates[] = {0, 1, 3, 7, 15};
    float best = p->C_verify[1];
    int best_d = 0;
    for each d:
        T = 1 + d;
        if (!supports(T)) continue;
        score = (C_verify[T] + C_draft[d]) / (1 + estimate_accept(d));
        if (score < best * 0.95) { best = score; best_d = d; }
    return best_d;
}
```

产出：

```text
src/vericurve_controller.cpp
src/vericurve_profile.h
patches/llamacpp_vericurve.diff
```

---

## 7. Phase 5: End-to-end evaluation

任务：

```text
1. Run baseline no speculation
2. Run fixed d=1,3,7
3. Run offline-best fixed d per workload
4. Run offline-best fixed d over mixed workload
5. Run goodput-only adaptive
6. Run VeriCurve
7. Run oracle
```

产出：

```text
results/e2e_tokens_per_sec.csv
results/oracle_gap.csv
results/regression_rate.csv
figures/
```

---

## 8. Phase 6: Paper writing

写作顺序：

```text
1. Motivation + failure of fixed speculation on RVV
2. C_verify/C_draft characterization
3. Curve model
4. Minimal curve-shaping kernels
5. Controller
6. Evaluation
```

---

## 9. 风险和 fallback

### Risk 1: C(T) 近线性

Fallback：

```text
转成 characterization paper：说明当前 RVV low-bit path 不适合 speculation，给出原因和 kernel requirements。
```

### Risk 2: T-specialized kernel 不够快

Fallback：

```text
减小目标，改做 Q4_0/Q8_0 microbenchmark + design study；或者转向 cache/draft cost characterization。
```

### Risk 3: Draft cost 太高

Fallback：

```text
聚焦 ngram draft，不使用 draft model。
强调 CPU/RVV 上 draft model 不适合，这是一个重要发现。
```

### Risk 4: Controller 不赢 best fixed d

Fallback：

```text
强调 cross-hardware/quantization deployment adaptation，而不是单 workload online adaptation。
```

### Risk 5: 工作量过大

Fallback：

```text
砍掉 T8/T16，只做 T1/T4。
砍掉多模型，只做 1B/3B。
砍掉 draft model，只做 ngram。
```

---

## 10. 一篇论文的最小 deliverables

```text
1. C_verify(T) and C_draft(d) profiler
2. One minimal T4 RVV verifier kernel
3. llama.cpp controller patch
4. Mixed workload benchmark
5. Full ablation table
```

---

## 11. 博士大论文扩展

后续可扩展：

```text
1. TianchenRV 自动生成 T-specialized kernels
2. intent/kernel certificates 给 curve-shaping kernel 提供正确性边界
3. 多后端：x86/ARM/GPU 对比
4. 更复杂 tree verification plan
5. agent-assisted curve search
```

