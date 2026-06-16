# 04. 成本模型与 Curve-aware Controller

## 1. 目标

VeriCurve-RV 的 controller 不是复杂调度器，也不是 RL/agent。它只解决一个问题：

> **当前应该 draft 几个 token？**

形式化：

```text
给定：
  C_verify(T)
  C_draft(d)
  E_accept(d)

选择：
  d ∈ {0,1,3,7,15}

使得：
  每个 committed token 的成本最低。
```

---

## 2. 基本模型

```text
J(d) = [ C_verify(1+d) + C_draft(d) ] / [ 1 + E_accept(d) ]
```

含义：

```text
分子：一次 speculation round 的成本
分母：这次 round 预计能提交几个 token
```

选择：

```text
d* = argmin_d J(d)
```

其中：

```text
T = 1 + d
```

---

## 3. 为什么必须包含 C_draft(d)

在 GPU 上，draft cost 有时可以被隐藏或相对 target 很小。但在 RISC-V/CPU 单用户场景：

```text
- draft 和 verifier 共享 CPU 核；
- draft model 也要读权重；
- memory bandwidth 竞争明显；
- draft cost 直接进入 critical path。
```

所以 `C_draft(d)` 必须实测，不能当成常数或忽略。

不同 draft source：

```text
ngram:
  C_draft 低，acceptance workload-dependent。

small draft model:
  C_draft 可能高，acceptance 可能更好。

MTP/self-speculative:
  成本结构取决于模型和实现。
```

---

## 4. 为什么不能只靠固定 draft length

固定 `d` 在单一 workload 和单一硬件上可能很好。但 VeriCurve-RV 的核心假设是存在漂移：

```text
1. C_verify(T) 跨硬件/量化/microkernel 漂移；
2. C_draft(d) 跨 draft source 漂移；
3. E_accept(d) 跨 workload 和生成过程漂移。
```

因此：

```text
optimal_d = f(C_verify(T), C_draft(d), E_accept(d))
```

如果 `E_accept(d)` 或 `C_verify(T)` 变化，固定 `d` 会系统性误选。

---

## 5. 单条曲线非单调不是唯一论证

理想情况是单条 `C_verify(T)` 曲线存在甜区和反弹：

```text
C(1)=1.0
C(2)=1.3
C(4)=1.8
C(8)=3.2
C(16)=7.0
```

但论文不能完全押在这个现象上。更稳的主论证是：

> **即使每条曲线都是单调次线性，只要不同部署/量化/microkernel 的斜率不同，再加上 acceptance 漂移，最优 draft length 也会变化。**

例子：

```text
Platform A:
  C(2)=1.4, C(4)=2.1, C(8)=4.0

Platform B:
  C(2)=1.2, C(4)=1.5, C(8)=2.2
```

同样的 acceptance rate 下，Platform A 可能最优 `d=1`，Platform B 可能最优 `d=3` 或 `d=7`。

---

## 6. C_verify(T) 的轻量解释模型

不要做过重的微架构模拟。建议模型只解释趋势：

```text
C_verify(T) ≈ C_fixed
            + C_weight_dequant(T)
            + C_compute(T)
            + C_acc_pressure(T, VLEN, LMUL)
            + C_cache_memory(T, model, quant)
```

各项意义：

```text
C_fixed:
  kernel dispatch, loop setup, batch construction overhead

C_weight_dequant(T):
  weight load/decode/scale cost，可能被多 RHS 摊薄

C_compute(T):
  dot/matmul arithmetic cost

C_acc_pressure:
  accumulator 数量、LMUL、register pressure、spill 风险

C_cache_memory:
  L2/L3 miss, DRAM bandwidth, model/quant size
```

目标不是精确预测每个 cycle，而是解释：

```text
- 为什么 T=4 可能比 T=1 更高效；
- 为什么 T=8 可能反弹；
- 为什么 Q4 和 Q8 的甜区不同；
- 为什么 VLEN/LMUL 改变会移动甜区。
```

---

## 7. Controller 伪代码

```pseudo
function choose_d(profile, stats, config):
    candidates = config.d_candidates  # [0,1,3,7,15]
    best_d = 0
    best_score = profile.C_verify[1]

    for d in candidates:
        T = 1 + d
        if not profile.supports_T(T):
            continue

        C_v = profile.C_verify[T]
        C_d = profile.C_draft[stats.draft_source][d]
        E_a = estimate_acceptance(stats, d)

        # avoid division by zero
        progress = 1.0 + max(0.0, E_a)
        score = (C_v + C_d + runtime_overhead(d)) / progress

        if score < best_score * (1.0 - config.switch_margin):
            best_score = score
            best_d = d

    return best_d
```

---

## 8. Acceptance estimator

最小实现：

```pseudo
accept_per_draft = accepted_tokens / drafted_tokens
EWMA = alpha * accept_per_draft + (1-alpha) * EWMA
E_accept(d) = min(d, d * EWMA)
```

更强版本：

```text
- 按 draft source 分桶
- 按 workload 分桶
- 按 recent context pattern 分桶
- 按 d 分桶
```

但单篇论文建议先做简单 EWMA + workload bucket。

---

## 9. Workload bucket

建议实现可选 workload hint：

```text
--vc-workload chat
--vc-workload code
--vc-workload rag
--vc-workload structured
--vc-workload auto
```

自动识别可以很粗糙：

```text
- code: prompt 中代码符号密度高
- structured: JSON/schema/tool-call 明显
- rag: context 很长且有重复模板
- chat: 默认
```

论文重点不是分类器，而是 acceptance drift。

---

## 10. Stability mechanisms

避免 controller 抖动：

```text
1. switch_margin: 预测收益大于 5% 才切换
2. update_interval: 每 8/16 token 更新一次
3. min_samples: 至少观察 N 次 draft 后才启用 adaptive
4. cooldown: 切换后 K token 内不再切换
```

---

## 11. 输出日志

每次 controller 决策记录：

```json
{
  "step": 128,
  "selected_d": 3,
  "selected_T": 4,
  "C_verify": 190.0,
  "C_draft": 0.1,
  "E_accept": 2.1,
  "score": 61.3,
  "actual_accept": 2,
  "fallback": false
}
```

这些日志直接用于论文分析。

---

## 12. 关键 ablation

必须证明 controller 不是多余的。

强 baseline：

```text
new T-specialized kernel + offline-best fixed d per workload
new T-specialized kernel + offline-best fixed d over mixed workload
goodput-only adaptive controller
oracle d
```

VeriCurve-RV 应该在 mixed workload / acceptance drift 场景里赢 fixed-d，并接近 oracle。

