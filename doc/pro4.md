这轮结果的含义很明确：**VeriCurve-RV 从“可能方向”变成了“值得继续做的主线”**。上一轮的 `direct R1T4` 失败没有杀死方向，反而帮我们定位了真正的设计点：**不是让 T 可见就行，而是必须做 RTile × TTile 的 verifier microkernel，把 `C_verify(T)` 曲线真正压弯。**

你现在的状态应该更新成：

```text
GO-characterization: yes
GO-curve-shaping-kernel: STRONG GO
GO-schedule-variant-mechanism: yes
GO-cache-mainline: no, supporting only
GO-controller-next-step: yes
FULL SYSTEM GO: not yet, conditional on draft/acceptance/controller
```

关键证据是这几个数：

```text
C_old_T4              = 48.085 ms
C_best_T1             = 12.024 ms
C_candidate_T4_total  = 16.826 ms
speedup_vs_old_T4     = 2.858×
curve_ratio           = 1.399
```

这说明新的 row-blocked `R8T4` verifier 不是一点点优化，而是把原来接近 `4×T1` 的 T=4 verification 压到了约 `1.4×T1`。这已经满足 **STRONG GO**。同一轮里还测到了 schedule variant crossover：T=1/2 时 old vec-dot 最好，T=4/8 时 R8 no-pack 最好，动态 variant selection 相比 best static 有 8.896% gain。cache-aware 目前只是 conditional supporting evidence，不是主线。

---

## 1. 这轮到底发生了什么？

你之前的失败是：

```text
R1T4 direct:
  one output row
  four token positions
```

它结果很差，说明：

```text
token-width visible alone 不够。
```

这轮成功的是：

```text
R8T4:
  eight output rows
  four token positions
```

这个结果非常重要，因为它说明真正有效的单位不是：

```text
single row × multiple tokens
```

而是：

```text
multiple rows × multiple tokens
```

也就是一个真正的 low-bit micro-GEMM / verifier tile。它同时利用了两类 reuse：

```text
R 方向：多个 output rows 复用 RHS activation block
T 方向：多个 token positions 摊薄 weight/dequant / verifier pass 成本
```

所以这轮给出的核心设计洞察是：

> **VeriCurve-RV 不能走“直接把 vecdot 扩成 T=4”的路线；它必须走 layout-aware RTile × TTile verifier microkernel 路线。**

这比之前的 “T-visible kernel” 更强，也更具体。

---

## 2. 这对最终 idea 的影响

最终 idea 现在应该定为：

# **VeriCurve-RV: Curve-Shaped Verification for Speculative LLM Inference on RISC-V Vector Processors**

中文：

# **VeriCurve-RV：面向 RISC-V 向量处理器投机推理的验证成本曲线塑形**

最核心的 thesis 应该写成：

> 在 llama.cpp/RVV low-bit 推理中，默认 verifier 路径把 T 个 token positions 退化成 T 次 single-RHS vec-dot，使 `C_verify(T)` 近似线性，导致 speculative verification 缺乏收益基础。VeriCurve-RV 通过 RTile × TTile low-bit RVV verifier microkernels 重塑 `C_verify(T)` 曲线，并让 runtime 根据这条曲线、draft cost 和 acceptance rate 选择 verifier variant 与 speculation budget。

注意这个 framing 很关键。不要写成：

```text
我们做 kernel-centric scheduler
```

也不要写成：

```text
我们根据 kernel profile 调 draft length
```

而要写成：

```text
我们先用 R×T verifier microkernel reshape C_verify(T)，
然后上层 speculation policy 才有可利用的成本结构。
```

这就避开了 TurboSpec / Sequoia / DISCO 这类 adaptive speculation 工作，也避开了 vLLM / Triton 早已有的 shape-conditioned kernel selection。

---

## 3. 这轮为什么是真正的转正？

因为你现在有了一个非平凡的因果链：

```text
旧 llama.cpp/RVV verifier:
  T=4 ≈ 4 × T=1
  speculation verification 没有物理收益基础

direct R1T4:
  失败，说明“只暴露 T”不是答案

row-blocked R8T4:
  T=4 ≈ 1.4 × best T=1
  这真正改变了 C_verify(T)

runtime variant crossover:
  T=1/2 用 old vec-dot
  T=4/8 用 R8 verifier

下一步:
  用新 C_verify(T) 决定 draft budget
```

这已经不是概念游戏了。它证明了 **microkernel design 可以塑形 verifier curve**。

从 speculative decoding 的成本公式看，这个结果也很有意义：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

如果 `d=3`，也就是 `T=4`，现在：

```text
C_verify(4) / C_verify(1) ≈ 1.399
```

如果 draft cost 很低，比如 n-gram draft，那么要超过 no-spec，只需要：

```text
E_accept(3) > 0.399 + C_draft(3) / C_verify(1)
```

也就是说，如果 draft cost 接近 0，平均接受 0.4 个 draft token 就可能有收益。这个门槛很低。
而旧路径是：

```text
C_old(4) / C_old(1) ≈ 4
```

那基本需要接近全部接受且 draft cost 极低才可能赚。这个差异就是你现在系统论文成立的基础。

---

## 4. 现在还不能宣布 full system 成功

虽然这轮是 STRONG GO，但还不能说整篇论文已经成立。原因是还缺三个关键数据：

```text
C_draft(d)
acceptance(d)
end-to-end controller result
```

也就是说，下一步必须回答：

1. ngram / draft model 在 RISC-V 上的 draft cost 会不会吃掉 R8T4 verifier 的收益？
2. 不同 workload 下 average accepted draft tokens 是否足够？
3. curve-aware controller 是否真的比 fixed draft length / goodput-only adaptive 更强？

如果最终发现：

```text
fixed d=3 在所有 workload 上都接近 oracle
```

那 controller 的贡献会弱化。
如果发现：

```text
chat 最优 d=0/1
code 最优 d=3/7
RAG/template 最优 d=3
```

那 controller 就有真实价值。

---

## 5. Schedule variant crossover 怎么用？

这轮 B 项也很有价值：

```text
best_static_latency  = 118.270 ms
best_dynamic_latency = 107.749 ms
dynamic_gain         = 8.896%
crossover_observed   = yes
```

这说明 runtime 不能只用一个 kernel。它至少需要：

```text
if T <= 2:
    use old vec-dot
elif T >= 4:
    use R8T4/R8 no-pack verifier
```

但这个不要作为主贡献来写。因为 “不同 shape 选不同 kernel” 本身不新；vLLM 的 `triton_scaled_mm` 就会根据 input shape 选择不同 block sizes / tile shape，IntentIR 里也已经有 host-side dispatch among pre-tuned variants 的相关思路。

所以它在论文里应该是：

```text
mechanism / necessary runtime support
```

不是：

```text
main novelty
```

主创新仍然是：

```text
R×T verifier microkernel reshapes C_verify(T)
```

---

## 6. Cache-aware 现在怎么处理？

Cache-aware 这条线现在是：

```text
CONDITIONAL
```

因为有 synthetic cache cliff：

```text
rows=2048 时 T16/T1 降到 10.157
rows<=512 基本接近 16
```

这说明 working set / cache 可能影响高 T 曲线，但现在没有 perf counter 证据，也没有多量化、多模型充分证明。所以不要把论文转成：

```text
Cache-Aware Speculative Decoding
```

更合适的是放在 cost model / explanation 里：

```text
C_verify(T) 由这些因素共同决定：
  R×T microkernel dataflow
  RVV VLEN / LMUL / register pressure
  weight/dequant reuse
  cache / working-set behavior
```

cache 是解释曲线形状的一个因素，不是总题目。

---

## 7. 和你的前两个课题怎么串？

现在三篇的关系更清楚了。

你的 IntentIR 已经证明：optimized kernel 里语义和 schedule 是纠缠的，所以它把算法语义、portable execution structure、non-binding schedule hints 分开；Layer C 里的 tile size、thread count、vector width、pipeline depth 可以被 retune，而不改变语义。IntentIR 的 RVV 后端也证明 retuning 有实际收益：RVV 相对 Triton-CPU LLVM baseline 有 4.48× single-thread 和 3.00× 16-thread speedup。

第三课题现在可以这样定位：

```text
IntentIR:
  kernel 可以被理解和重调。

TianchenRV:
  kernel 可以面向 RISC-V 生成和优化。

VeriCurve-RV:
  kernel 的 verifier cost curve 可以被 microkernel 设计塑形，
  并进入推理框架的 speculative decoding decision。
```

这条线比“kernel 写作门槛降低，所以框架要接 kernel”强很多。它是：

> **kernel understanding → kernel generation → kernel curve drives inference policy**

---

## 8. 下一步应该怎么做？

现在不需要再做 kernel feasibility。A 已经 STRONG GO。
下一轮应该进入：

```text
curve-aware-controller-feasibility
```

目标不是马上写完整系统，而是判断：

```text
新的 R8T4 curve 是否真的能转化成 speculation throughput
```

我建议 agent 下一轮按下面做。

---

# 给 agent 的下一轮任务

任务名：

```text
06-17-curve-aware-controller-feasibility
```

目标：

```text
Determine whether the shaped R8T4 verifier curve produces real speculation-budget choices and end-to-end gains.
```

---

## Task 1：固化 C_verify_best(T)

基于 row-blocked R8T4 和 old vec-dot，测：

```text
T = 1, 2, 4, 8, 16
variants:
  old_vecdot
  R8T4 / R8 no-pack
  best_dynamic
```

输出：

```text
C_verify_old(T)
C_verify_R8(T)
C_verify_best(T)
winner_variant(T)
C_verify_best(T) / C_verify_best(1)
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
  and winner variant changes across T.

CONDITIONAL:
  C_best(4) / C_best(1) <= 2.5

NO-GO:
  C_best(4) / C_best(1) > 3.0
```

根据这轮结果，大概率 GO。

---

## Task 2：测 C_draft(d)

优先 cheap draft：

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

必须拆开：

```text
draft-only cost
verify cost
total predicted cost
```

产物：

```text
results/C_draft.csv
research/C_draft.md
```

关键问题：

```text
CPU/RVV 上 draft cost 是否会吃掉 R8T4 的 verifier 曲线收益？
```

---

## Task 3：测 acceptance(d)

workload 至少四类：

```text
chat / random QA
code completion or code refactor
RAG/template
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
  所有 workload 最优 d 一样，
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

最关键的现象：

```text
old_curve:
  high-acceptance workload 也可能不值得投机

new_R8_curve:
  high-acceptance workload 适合 d=3/7
  low-acceptance workload 仍然 d=0/1
```

这能证明：

```text
curve shaping changes the viable speculation region
```

---

## Task 5：最小 controller

实现要非常轻：

```text
profile table:
  C_verify(T)
  C_draft(d)

runtime:
  maintain recent E_accept(d)
  every 8 or 16 generated tokens update decision
  choose d ∈ {0, 1, 3, 7}
```

不要上 RL，不要 agent，不要复杂在线 tuning。

baseline 必须包括：

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

## 9. 现在应该怎么记录项目状态？

建议更新成：

```text
GO-characterization: yes
GO-current-path-gap: yes
NO-GO-direct-R1T4: yes
GO-RTile×TTile-curve-shaping: STRONG GO
GO-runtime-variant-selection: yes
GO-controller-feasibility: next
FULL-SYSTEM-GO: conditional
```

这句话也可以写进 Trellis spec：

> Direct token-width exposure failed. VeriCurve-RV’s viable kernel substrate is row-and-token blocked verifier microkernels. The controller must use the shaped RTile × TTile verifier curve, not direct R1T4.

---

## 最终判断

这轮是好结果。它说明：

1. 旧 llama.cpp/RVV path 确实有 kernel gap；
2. 直接 T-visible vecdot 失败，说明简单想法不够；
3. R8T4 成功，说明真正的 curve shaping 可行；
4. schedule variant crossover 存在，说明 runtime 选择有必要；
5. 下一步可以进入 controller，但 full paper 还要看 draft cost 和 acceptance。

所以最终方向应该继续，但要改得更准：

> **VeriCurve-RV：通过 RTile × TTile low-bit RVV verifier microkernels 重塑 speculative verification 的成本曲线，并基于这条曲线做 draft budget 和 verifier variant 选择。**

这就是现在的情况。


情况是：**VeriCurve-RV 现在已经从“kernel 可行性”进入了“controller 是否能成为论文贡献”的阶段。**

这轮结果不是 No-Go。它说明：

```text
curve-shaping kernel: 已经成立
schedule variant crossover: 已经成立
controller: 有价值迹象，但还没有强到 full system GO
```

我会把当前状态判成：

```text
GO: VeriCurve-RV 主线继续
GO: RTile × TTile verifier kernel 作为核心使能机制
GO: curve-aware controller 可以继续验证
CONDITIONAL: controller 还没达到强论文标准
NO-GO: 不能现在就宣称完整系统成功
```

---

# 1. 这轮结果到底说明了什么？

之前一轮已经证明：

```text
direct R1T4 不行
row-blocked R8T4 行
```

这个结论很关键：当前可行路线不是“让 T 可见”，而是 **RTile × TTile verifier microkernel 重塑 C_verify(T) 曲线**。上一轮 final summary 里也已经给了非常强的 kernel 证据：

```text
C_old_T4 = 48.085 ms
C_best_T1 = 12.024 ms
C_candidate_T4_total = 16.826 ms
speedup_vs_old_T4 = 2.858×
curve_ratio = 1.399
```

也就是说，R8T4 把原来接近 `4×T1` 的 T=4 verification cost 压到了约 `1.4×best_T1`，这是 STRONG GO。

这轮新结果进一步证明了第二件事：

> **这个被重塑的新 C_verify(T) 曲线确实会改变 speculation decision。**

你的报告里说：

```text
old curve:
  所有 workload 最优 d=0

new curve:
  chat 最优 d=0
  code / rag / structured 最优 d=3
```

这就是我们一直想要的因果链：

```text
R8T4 verifier kernel
  -> C_verify(T) 从线性变成可摊薄
  -> high-acceptance workload 下 speculation 变得有意义
  -> runtime policy 不再是固定 d 或永远 d=0
```

这个结果已经足够证明 **controller 方向有研究价值**。

---

# 2. 为什么还不是 FULL SYSTEM GO？

因为现在的 controller 结果是：

```text
no speculation:              12.024 ms/token
offline-best fixed mixed:     9.048 ms/token
VeriCurve-RV offline:         8.226 ms/token
oracle:                       7.190 ms/token
```

VeriCurve-RV 比 mixed fixed 最优快约：

```text
9.048 / 8.226 - 1 ≈ 10.0%
```

这个很好，说明它不是随便打一个弱 baseline。

但它只达到 oracle 的：

```text
7.190 / 8.226 ≈ 87.4%
```

没有过你们设的 `>=90% oracle` full-system gate。

所以准确判断是：

```text
CONDITIONAL PAPER GO
not FULL SYSTEM GO
```

这不是坏消息。它说明方向已经接近成立，但还有一个 gap：

> **当前 controller 还没有把 per-step / per-workload 的 acceptance drift 利用到足够好。**

下一轮应该验证：这个 87.4% 到 90% 的差距，是因为当前只是 offline/proxy controller，还是因为 controller 本身天花板就在那里。

---

# 3. 当前最危险的问题是什么？

我认为现在最大风险有五个。

## 风险 1：acceptance 还不是完整真实 llama.cpp trace

报告里说下一步要用真实 llama.cpp 输出 trace 或 controlled self-speculative path 替换 deterministic ngram proxy，这个判断是对的。

现在的结论基于：

```text
C_verify(T)
C_draft(d)
proxy acceptance
offline J(d)
```

这还不是完整的真实 speculative decoding loop。

真实系统里 acceptance 会受这些影响：

```text
sampling strategy
temperature / top-p
模型输出分布
prompt phase
repeated tokens
code vs chat vs structured output
draft source
```

如果真实 acceptance 和 proxy acceptance 差很多，当前 J(d) 结论会变。

## 风险 2：offline controller 不是 online controller

现在的 VeriCurve-RV offline 结果很好，但 real runtime 需要在线估计：

```text
recent acceptance
current workload phase
switching hysteresis
decision window
```

如果 online EWMA 太慢，会错过 workload 切换；如果太快，会因为 noise 频繁切换。

所以不能直接把 offline result 当成 full system result。

## 风险 3：d=15 暂时不应该进入主 claim

报告里已经说：

```text
d=15 暂时弱一些，因为 T=16 还是两个 R8T8 tile 的组合估计，不是 native R8T16 测量
```

这个判断对。

主论文第一版应该聚焦：

```text
d ∈ {0, 1, 3, 7}
T ∈ {1, 2, 4, 8}
```

不要把 `d=15` 放在核心结果里，除非你们真的做了 native R8T16 或可靠 T16 path。

## 风险 4：还缺 end-to-end integration 证据

现在 C_verify 是强证据，但 reviewer 会问：

```text
这个 R8T4 verifier kernel 真的进入了 llama.cpp speculative verification path 吗？
还是只是 microbenchmark / offline model？
```

下一步必须至少做一个 controlled integration：

```text
llama.cpp speculative verification path
  -> uses best verifier variant for T=4
  -> logs selected variant
  -> measures end-to-end accepted-token latency
```

没有这个，论文容易被认为还是 kernel + offline analysis。

## 风险 5：强 baseline 还要补齐

现在已经打了 `offline-best fixed mixed`，很好。下一轮还要明确比较：

```text
offline-best fixed d per workload
goodput-only adaptive
VeriCurve online EWMA
oracle replay
```

尤其是 **goodput-only adaptive** 很重要。因为 TurboSpec 一类工作会说：我不用 C_verify 模型，只看 goodput，也能调。你要证明：

```text
VeriCurve 的 curve-aware input 帮助它更快、更稳、更少探索。
```

否则 reviewer 会说这是普通 adaptive speculation。

---

# 4. 现在最终 idea 要不要改？

不需要大改，但应该再精炼一下。

我建议最终 title / thesis 定成：

# **VeriCurve-RV: Curve-Shaped Verification for Speculative LLM Inference on RISC-V Vector Processors**

中文：

> **VeriCurve-RV：面向 RISC-V 向量处理器投机推理的验证成本曲线塑形**

核心主张：

> **当前 llama.cpp/RVV low-bit verifier path 近似 repeated single-RHS vecdot，使 `C_verify(T)` 基本线性；direct T-visible R1T4 不足以改善曲线。VeriCurve-RV 通过 layout-aware RTile × TTile verifier microkernels 重塑 `C_verify(T)`，并让 runtime 根据新曲线、draft cost 和 acceptance drift 选择 verifier variant 与 draft budget。**

这个版本比 “kernel-centric scheduler” 更强，因为它明确指出了三个事实：

```text
1. 旧曲线线性；
2. RTile × TTile kernel 能 reshape 曲线；
3. reshape 后的曲线改变 speculation decision。
```

这正好对应你们已经得到的证据链。

---

# 5. 和你前两个课题的关系

现在这个方向和 IntentIR / TianchenRV 反而更顺了。

IntentIR 的论文已经明确说，它的三层表示把 algorithmic intent、portable execution structure、non-binding schedule hints 分开；后端可以 retune Layer C，而不把 source schedule 当成语义。它在 RVV 上也已经展示了 retuning 和 explicit RVV lowering 的价值：RVV 后端相对 Triton-CPU LLVM baseline 有 4.48× single-thread 和 3.00× 16-thread geomean speedup。

所以博士叙事可以是：

```text
IntentIR:
  kernel 的语义和 schedule 可以被拆开。

TianchenRV:
  RISC-V/RVV kernel 可以被生成和调优。

VeriCurve-RV:
  kernel 的成本曲线可以被设计，并进入推理框架的 decoding decision。
```

但单篇论文里仍然建议不要强依赖 IntentIR/TianchenRV。你可以把 R8T4 kernel 写成：

```text
a minimal hand-written or generated RVV verifier microkernel
```

博士大论文里再把 TianchenRV 串进去。

---

# 6. 下一步让 agent 做什么？

现在不要继续卷 kernel，也不要再做 abstract framing。下一步应该开一个新 task：

```text
06-17-real-online-controller-validation
```

目标：

```text
Turn the current offline/proxy controller result into real llama.cpp trace and online-controller evidence.
```

下面这段可以直接给 agent。

---

## Task 0：继承当前状态

在 PRD 写：

```text
Previous status:
  Curve-shaping kernel: STRONG GO
    C_best(4)/C_best(1) = 1.399
    speedup_vs_old_T4 = 2.858×

  Schedule crossover: GO
    T=1/2 old vecdot wins
    T>=4 row-blocked RTile x TTile wins

  Controller offline: CONDITIONAL PAPER GO
    no speculation = 12.024 ms/token
    best fixed mixed = 9.048 ms/token
    VeriCurve offline = 8.226 ms/token
    oracle = 7.190 ms/token
    VeriCurve beats fixed mixed by 10.0%
    VeriCurve reaches 87.4% oracle

Goal:
  Determine whether real acceptance trace + online EWMA controller
  can promote controller from CONDITIONAL PAPER GO to FULL SYSTEM GO.
```

---

## Task 1：真实 llama.cpp acceptance trace

不要继续用 deterministic proxy。要在真实 llama.cpp / controlled self-speculative path 中记录：

```text
prompt_id
workload_type
step_id
draft_source
requested_d
draft_tokens
target_tokens
accepted_count
acceptance_prefix_length
selected_T
selected_verifier_variant
verify_latency_ms
draft_latency_ms
total_latency_ms
```

workload 至少四类：

```text
chat / random QA
code completion or refactor
RAG/template-like prompt
structured output / JSON-like output
```

设置：

```text
d ∈ {1,3,7}
temperature = 0 first
then optional temp > 0
```

产物：

```text
results/real_acceptance_trace.csv
research/real_acceptance_trace.md
patches/llamacpp_acceptance_trace.patch
```

### Go/No-Go

```text
GO:
  real acceptance still shows workload drift:
    low-acceptance workload best d=0/1
    at least one high-acceptance workload best d=3/7

CONDITIONAL:
  acceptance drift exists but weaker than proxy

NO-GO:
  all workloads have low acceptance
  or all workloads prefer same d
```

---

## Task 2：real C_draft(d) and C_verify(T) under integrated path

现在要测 integrated path，不只是 microbench。

对每个 `d`：

```text
T = 1 + d
```

记录：

```text
C_draft_real(d)
C_verify_real(T)
selected verifier variant
total step latency
accepted tokens
```

必须确认：

```text
T=4 actually uses R8T4/R8 no-pack verifier
T=1/2 uses old vecdot if still best
```

产物：

```text
results/integrated_cost_trace.csv
research/integrated_cost_trace.md
```

### Go/No-Go

```text
GO:
  integrated C_verify(4)/C_verify(1) <= 1.8
  and selected variant matches expected crossover

CONDITIONAL:
  integrated C_verify(4)/C_verify(1) <= 2.5

NO-GO:
  integrated path loses curve shaping
  or R8T4 cannot be used in real path
```

这个 gate 非常关键。
如果 integrated path 里 R8T4 的优势消失，那 full system 会退回 kernel/microbench paper。

---

## Task 3：online EWMA controller

实现一个非常简单的 controller，不要 RL，不要 agent。

候选：

```text
d ∈ {0,1,3,7}
```

输入：

```text
C_verify(T) table
C_draft(d) table
recent acceptance estimate
```

更新：

```text
window = 8 or 16 tokens
EWMA alpha = 0.2 or 0.3
switch margin = 5%
minimum dwell = 2 windows
```

目标函数：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

产物：

```text
patches/online_ewma_controller.patch
results/online_controller_trace.csv
research/online_controller.md
```

### 必须记录

```text
step_id
old_d
new_d
estimated_acceptance
actual_acceptance
estimated_J(d)
actual_J(d)
switch_reason
```

---

## Task 4：强 baseline 对比

baseline 必须包括：

```text
B0 no speculation
B1 fixed d=1
B2 fixed d=3
B3 fixed d=7
B4 offline-best fixed d over mixed workload
B5 offline-best fixed d per workload
B6 goodput-only adaptive
B7 VeriCurve online EWMA
B8 oracle replay
```

指标：

```text
ms / emitted token
tokens / second
regression on low-acceptance workload
controller overhead
oracle reach
switch count
```

产物：

```text
results/controller_e2e_summary.csv
research/controller_e2e_summary.md
```

### Full System Go/No-Go

```text
FULL SYSTEM GO:
  VeriCurve online beats offline-best fixed mixed by >= 8%
  and reaches >= 90% oracle
  and does not regress no-spec on low-acceptance workloads by > 3%
  and controller overhead < 1%

STRONG PAPER GO:
  VeriCurve online beats goodput-only adaptive by >= 5%
  and reaches >= 90% oracle

CONDITIONAL PAPER GO:
  VeriCurve beats default/fixed but not offline-best or not 90% oracle

NO-GO controller:
  offline-best fixed d or goodput-only adaptive is within 3-5% of VeriCurve
```

---

## Task 5：d=15 暂时降级

不要把 d=15 放进主线，除非 agent 先完成：

```text
native T=16 verifier measurement
```

否则所有 d=15 结果只放 appendix / exploratory。

---

# 7. 如果下一轮还是 87-89% oracle，怎么办？

如果在线 controller 还是达不到 90% oracle，但能稳定赢 mixed fixed 8-10%，我建议不要硬追 full system。论文可以降级但仍然有价值：

```text
主贡献：
  1. old RVV verifier curve linear
  2. direct R1T4 no-go
  3. R8T4 curve shaping strong-go
  4. curve-aware offline policy beats best mixed fixed
```

这种论文更像：

> **curve-shaping verifier kernels + policy analysis**

而不是完整在线 serving system。

如果想冲强系统论文，必须补：

```text
real online controller
goodput-only adaptive comparison
end-to-end latency
```

---

# 8. 最终当前判断

我会把当前状态写成：

```text
VeriCurve-RV: continue.

Kernel result:
  STRONG GO.

Policy result:
  CONDITIONAL PAPER GO.

Full system:
  not yet.

Next decisive experiment:
  real llama.cpp acceptance trace + online EWMA controller.
```

一句话总结：

> **你们现在已经证明了 VeriCurve-RV 的核心物理基础：R8T4 verifier kernel 能把 RISC-V low-bit verification curve 从线性压成可用曲线；也初步证明了这条曲线会改变 draft budget。下一步不是再想 idea，而是把 offline/proxy controller 变成真实 llama.cpp 在线 controller。如果它能过 90% oracle 和强 baseline，full system 论文成立；如果过不了，也至少保留一篇 curve-shaping + policy-analysis 论文。**
