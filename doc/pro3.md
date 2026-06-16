这个结果非常关键，而且方向**明显转正**了。

我现在的判断是：

```text
VeriCurve-RV 继续做。
但主线必须从 “T-visible verifier kernel” 改成
“RTile × TTile curve-shaping verifier kernel + curve-aware speculation”。
```

这次不是小修小补，而是把最终 idea 的中心确定下来了。

---

# 1. 这轮结果说明了什么？

这轮实验把之前最重要的未知项打穿了。

旧路径已经确认：

```text
current llama.cpp/RVV Q4_0 × Q8_0:
  T=1/2/4/8 基本是 repeated T1
  真实路径是 ggml_vec_dot_q4_0_q8_0, nrc=1
```

之前 direct R1T4 失败：

```text
R=1, T=4 direct vecdot:
  正确性 OK
  性能比 4×T1 还慢
```

这说明：

```text
只让 token-width 可见不够。
```

但现在新的 row-blocked R8T4 成功了：

```text
C_old_T4 = 48.085 ms
C_best_T1 = 12.024 ms
C_candidate_T4_total = 16.826 ms
speedup_vs_old_T4 = 2.858×
curve_ratio = 1.399
```

也就是说，新的 R8T4 verifier 让：

```text
T=4 verification cost
从接近 4×T1
压到了约 1.4×best_T1
```

这是非常强的 curve shaping。agent 的 final summary 也明确给出 **Curve-Shaping Kernel = STRONG GO**，并指出 direct R1T4 失败，但 row-blocked R8T4 成功，真正可行路线是 layout-aware RTile × TTile verifier kernel，而不是 direct T wrapper。

这个结果把论文从“有点像 profiling/controller”拉回到了一个更强的 kernel-systems 协同点：

> **不是框架根据已有 kernel 曲线做调度，而是我们设计 microkernel 来重塑 verifier cost curve，然后框架根据这条新曲线做投机推理决策。**

---

# 2. 为什么 R8T4 成功，而 R1T4 失败？

这点很重要，因为它会变成论文的设计洞察。

之前的失败路径是：

```text
R1T4:
  one output row
  four token positions
```

它只在 T 维度做了扩展。理论上它可以复用一行 Q4 weight 的 decode，但它没有同时利用 output row 维度。实际结果说明这种 reuse 不够，甚至破坏了原来 vecdot 的优化结构。

现在成功的是：

```text
R8T4:
  eight output rows
  four token positions
```

这更接近真正的 low-bit micro-GEMM，而不是 vecdot 的简单扩展。

它可能同时获得了几类收益：

```text
1. 多个 output rows 复用 RHS activation block；
2. 多个 token positions 复用 weight/dequant 路径；
3. R × T micro-tile 给 RVV accumulator 和 load pattern 更好的组织空间；
4. 不再把 matmul 拆成大量 row-token scalar dot。
```

所以最终论文里要明确写：

> **T visibility alone is insufficient. Curve shaping requires a two-dimensional verifier microkernel that jointly blocks output rows and token positions.**

中文就是：

> **只暴露 token-width 不够，必须把 verifier kernel 从 single-row vecdot 改造成 RTile × TTile 的 low-bit micro-GEMM。**

这个是一个实打实的设计发现。

---

# 3. Schedule variant crossover 也成立，但它是 secondary mechanism

agent 的结果里第二个重要点是：

```text
number_of_variants = 5
best_static_latency = 118.270 ms
best_dynamic_latency = 107.749 ms
dynamic_gain = 8.896%
crossover_observed = yes
```

而且：

```text
T=1/2 最优是 old vec-dot
T=4/8 最优是 R8 no-pack
```

这说明 runtime variant selection 有真实意义。它不是泛泛说“不同 shape 选不同 kernel”这么普通，而是在你的实际 RVV verifier path 上出现了明确 crossover：

```text
small T:
  old vecdot 更好

larger T:
  R8T4/R8 no-pack 更好
```

这很适合放进系统设计里，但不要把它写成主贡献。主贡献仍然应该是：

```text
curve-shaped verifier kernel creates a non-linear C(T)
```

Schedule variant selection 是系统内机制：

```text
given T, choose old vecdot or R8 verifier path
```

换句话说：

```text
Crossover 支持 VeriCurve-RV 的 runtime dispatch 层；
但论文的核心新意不是 runtime dispatch 本身。
```

这个边界很重要，因为 vLLM 已经有 shape-conditioned kernel selection。比如 vLLM 的 `triton_scaled_mm` 会根据 `input.shape` 的 M/K/N 选择 Triton 的 `BLOCK_SIZE_M/N/K`，vLLM IR 也明确在做 operator semantics 与 implementation/dispatch 的分离和 kernel selection。([vLLM][1])

所以你不能说：

> 我们发现不同 shape 选不同 kernel。

应该说：

> **我们通过 RTile × TTile verifier microkernel 改变了 verifier cost curve，并且 runtime dispatch 只是使用这条曲线的必要机制。**

---

# 4. Cache-aware 现在降级为解释，不是主线

agent 给的 cache 结论是：

```text
Cache-aware characterization: CONDITIONAL
rows=2048 时 T16/T1 降到 10.157
rows<=512 基本接近 16
cache_counter_correlation = not measured
synthetic_cache_cliff = yes
```

这说明 cache / working-set 确实可能影响高 T 曲线，但证据还不够强，不能当主线。final summary 也明确说 cache behavior 是 supporting evidence，而不是 primary direction。

所以现在不要转成：

```text
Cache-aware speculative decoding
```

应该把 cache 放到 cost model 或 characterization 的解释层：

```text
C_verify(T) 的形状可能来自：
  R×T microkernel dataflow
  RVV VLEN/LMUL/register pressure
  weight/dequant reuse
  cache/working-set effects
```

其中 cache 是一个因素，不是论文总抽象。

---

# 5. 最终 idea 应该怎么定？

我建议最终题目定为：

# **VeriCurve-RV: Curve-Shaped Verification for Speculative LLM Inference on RISC-V Vector Processors**

中文：

# **VeriCurve-RV：面向 RISC-V 向量处理器投机推理的验证成本曲线塑形**

更完整的论文 thesis：

> **在 llama.cpp/RVV low-bit 推理中，默认 verifier 路径把 T 个 token positions 退化为 T 次 single-RHS vecdot，使 `C_verify(T)` 近似线性，导致 speculative verification 缺乏收益基础。VeriCurve-RV 通过 RTile × TTile low-bit RVV verifier microkernels 重塑 `C_verify(T)` 曲线，并让 runtime 根据这条曲线、draft cost 和 acceptance rate 选择 verifier variant 与 speculation budget。**

一句更短的：

> **VeriCurve-RV 不是把 kernel 当黑箱调度，而是先用 microkernel 设计塑造 verifier cost curve，再让推理框架根据这条曲线做投机决策。**

这比 “kernel-centric scheduler” 更具体，也比 “adaptive speculation on RISC-V” 更有新意。

---

# 6. 这和已有工作的边界

你现在可以非常清楚地区分三类已有工作。

## vLLM / Triton / cuBLASLt

它们做的是：

```text
given shape -> choose kernel / tile / algorithm
```

这不新，不能作为 claim。vLLM `triton_scaled_mm` 的 shape-conditioned BLOCK 参数就是实证例子；cuBLASLt 也有 matmul heuristic 和 heuristic cache。([vLLM][1])

你的不同点是：

```text
microkernel design -> reshape C_verify(T)
C_verify(T) -> drive speculation policy
```

不是简单：

```text
shape -> kernel
```

## SmartSpec / TurboSpec / DISCO / Sequoia

它们做的是：

```text
given verifier backend -> adapt speculation length / tree
```

SmartSpec/Goodput 论文就明确说 speculation length 没有一个适合所有 workloads 的固定值，所以动态根据 load 和 speculation accuracy 决定。([arXiv][2])

你的不同点是：

```text
verifier backend itself is changed and measured;
C_verify(T) is not a fixed black-box curve.
```

也就是说，你不是只在已有 curve 上调 d，而是通过 R8T4 这类 microkernel 把 curve 从线性变成可用，然后再调 d。

## IntentIR / TianchenRV

这篇第三课题也不要硬依赖 IntentIR，但博士叙事上它很顺。

IntentIR 已经提出三层表示：Layer A 是算法语义，Layer B 是 portable execution structure，Layer C 是非绑定 schedule hints；后端可以 retune Layer C，而不是把 source schedule 当语义冻结。 它的 RVV 结果也显示 retuning 比 freeze-tiling 有收益，并且在 RVV 上相对 Triton-CPU LLVM baseline 有 4.48× single-thread、3.00× 16-thread geomean speedup。

所以三课题可以这样串：

```text
IntentIR:
  kernel 可以被理解，语义和 schedule 可以分离。

TianchenRV:
  kernel 可以被生成 / retune 到 RISC-V。

VeriCurve-RV:
  kernel 的 verifier cost curve 可以被设计，
  并进入推理框架的 decoding decision。
```

---

# 7. 现在 controller 可以做了吗？

可以进入 controller 阶段，但要非常克制。

agent 说：

```text
Controller readiness: READY
reason: A is STRONG GO and B is GO
```

我同意，但这个 READY 的含义是：

```text
可以开始测 C_draft / acceptance / minimal controller
```

不是说：

```text
现在就能写 full system paper
```

下一步必须回答两个问题：

```text
1. 在新 R8T4 verifier curve 下，哪些 d 有预测收益？
2. 相比 fixed-best draft length，curve-aware controller 是否真有边际价值？
```

如果 fixed d=3 在所有 workload 上都接近 oracle，那 controller 不强。
如果不同 workload / quant / model 下最优 d 漂移，controller 才强。

---

# 8. 下一步最该让 agent 做什么？

现在不要再继续 kernel feasibility 了，已经 STRONG GO。下一轮应该开：

```text
06-17-curve-aware-controller-feasibility
```

目标：

```text
Determine whether the row-blocked R8T4 verifier curve creates
real speculation budget choices and end-to-end gains.
```

具体任务：

## Task 1：生成新的 C_verify(T) table

基于本轮成功 kernel，测：

```text
T = 1, 2, 4, 8, 16
variants:
  old vecdot
  R8T4 / R8 no-pack
  best dynamic variant
```

必须输出：

```text
C_verify_old(T)
C_verify_new(T)
C_verify_best(T)
winner_variant(T)
```

产物：

```text
results/C_verify_best_curve.csv
research/C_verify_best_curve.md
```

Go/No-Go：

```text
GO:
  C_best(4) / C_best(1) <= 1.8
  and at least one crossover T exists.

CONDITIONAL:
  C_best(4) / C_best(1) <= 2.5

NO-GO:
  C_best(4) / C_best(1) > 3.0
```

目前从 final summary 看，T=4 已经是 1.399，所以应该 GO。

---

## Task 2：测 C_draft(d)

先不要上大 draft model。优先 cheap draft：

```text
ngram-simple
ngram-map
ngram-mod
```

可选：

```text
small draft model
```

测：

```text
d = 1, 3, 7, 15
C_draft(d)
```

要分：

```text
draft-only cost
verification cost
total cost
```

产物：

```text
results/C_draft.csv
research/C_draft.md
```

关键判断：

```text
CPU/RVV 上 draft cost 是否吃掉 R8T4 verifier curve 的收益？
```

---

## Task 3：测 acceptance(d)

workload 至少四类：

```text
chat / random QA
code completion or code refactor
RAG/template style
structured output / repeated JSON-like output
```

记录：

```text
E_accept(d)
acceptance distribution
not just average
```

产物：

```text
results/acceptance_by_workload.csv
research/acceptance_by_workload.md
```

Go/No-Go：

```text
GO:
  至少两个 workload 的 optimal d 不同；
  至少一个 workload 适合 d=3 或 d=7；
  至少一个低 acceptance workload 适合 d=0 或 d=1。

NO-GO:
  所有 workload 最优 d 都一样，
  或所有 d>0 都不划算。
```

---

## Task 4：离线计算 J(d)

公式：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

对每个 workload 输出：

```text
best_d_old_curve
best_d_new_curve
best_d_oracle
predicted_speedup_vs_no_spec
predicted_speedup_vs_fixed_d
```

产物：

```text
results/Jd_offline_prediction.csv
research/Jd_offline_prediction.md
```

最关键的现象是：

```text
old_curve 下 best_d 可能是 0/1；
new_curve 下 high-acceptance workload best_d 变成 3/7；
low-acceptance workload 仍然 d=0/1。
```

这比之前那个“旧线性/新次线性 decision flip”更强，因为它要结合 real C_draft 和 real acceptance。

---

## Task 5：最小 controller

实现不要复杂：

```text
profile table:
  C_verify(T)
  C_draft(d)

runtime:
  maintain recent E_accept(d)
  every 8 or 16 generated tokens update decision
  choose d ∈ {0,1,3,7}
```

baseline 必须强：

```text
B0 no speculation
B1 llama.cpp fixed default
B2 fixed d=3
B3 offline-best fixed d per workload
B4 offline-best fixed d over mixed workload
B5 goodput-only adaptive
B6 VeriCurve-RV
B7 oracle
```

Go/No-Go：

```text
FULL SYSTEM GO:
  VeriCurve-RV beats offline-best fixed d over mixed workload by >= 8-10%
  and reaches >= 90% oracle
  and no regression on low-acceptance workload.

CONDITIONAL PAPER GO:
  VeriCurve-RV beats default/fixed,
  but not offline-best fixed d.

NO-GO controller:
  offline-best fixed d or goodput-only adaptive matches within 3-5%.
```

---

# 9. 论文结构现在可以初步定了

如果下一步 controller 也有结果，论文结构应该是：

## Problem

RISC-V/llama.cpp low-bit verifier path is repeated single-RHS vecdot:

```text
C_old(T) ≈ T × C_old(1)
```

This makes speculative verification unattractive.

## Design lesson

Direct T-visible R1T4 is insufficient and slower.

## Key contribution

RTile × TTile verifier microkernels reshape the verifier curve:

```text
R8T4:
  C(4) = 1.399 × best_T1
  2.858× faster than old_T4
```

## System

Use shaped verifier curves to select:

```text
verifier variant
speculation budget
```

## Evaluation

Show:

```text
current path trace
direct R1T4 no-go
R8T4 strong-go
variant crossover
C_draft + acceptance
end-to-end controller
```

---

# 10. 当前最终结论

这轮结果非常好。它把研究点从“可能有趣”变成了“有真实物理基础”。

现在的最终 idea 应该是：

> **VeriCurve-RV：通过 RTile × TTile low-bit RVV verifier microkernels 重塑 speculative verification 的成本曲线，并让 llama.cpp runtime 根据新曲线选择 verifier variant 和 draft budget。**

一句话中文：

> **不是让 kernel 被动接受推理框架给出的 T，也不是只根据 profile 调 draft length，而是先用 R×T microkernel 把 RISC-V verifier curve 从线性变成可利用，再让推理框架围绕这条曲线做投机决策。**

当前状态：

```text
GO-characterization: yes
GO-curve-shaping-kernel: STRONG GO
GO-schedule-variant-mechanism: GO
GO-cache-mainline: no, only supporting
GO-controller-next-step: yes
FULL PAPER GO: conditional on controller / draft / acceptance
```

所以现在应该继续 VeriCurve-RV 系统线。下一轮不再做 kernel 可行性，而是做：

```text
C_verify_best(T)
C_draft(d)
acceptance(d)
J(d)
minimal controller
```

这就是下一阶段的 Go/No-Go。

[1]: https://docs.vllm.ai/en/v0.14.0/api/vllm/model_executor/layers/quantization/compressed_tensors/triton_scaled_mm.html?utm_source=chatgpt.com "triton_scaled_mm - vLLM"
[2]: https://arxiv.org/abs/2406.14066?utm_source=chatgpt.com "Optimizing Speculative Decoding for Serving Large Language Models Using Goodput"
