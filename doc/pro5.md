这轮结果的核心情况是：

```text
VeriCurve-RV 主线继续。
R8T4 curve-shaping 仍然是强结果。
但 controller 贡献还没有被真实在线实验坐实。
当前是 CONDITIONAL PAPER GO，不是 FULL SYSTEM GO。
```

这不是坏结果。它说明你们已经从“能不能改曲线”推进到了“这个曲线能不能支撑一个真正 adaptive controller”的阶段。上一轮已经确认 curve-shaping kernel 是 STRONG GO：`C_old_T4=48.085ms`、`C_best_T1=12.024ms`、`C_candidate_T4_total=16.826ms`，也就是 R8T4 把 T=4 从接近 4×T1 压到了 1.399×T1，并且 T=1/2 与 T=4/8 之间确实出现 variant crossover。

这一轮的新信息是：**controlled lookup 设置下，d=3 对所有 workload 都是最优。** 这对 curve-shaping 是好消息，因为它说明 R8T4 让 T=4 verification 变得非常划算；但对 controller 贡献是压力，因为 fixed `d=3` 变成了一个很强的 baseline。

---

## 1. 这轮结果说明了什么？

你们现在有三条已成立的事实。

第一，**真实 llama.cpp lookup / trace plumbing 打通了。**

`llama-lookup` 和 `llama-lookup-stats` 能在 RVV 上跑，per-step trace 能记录 `requested_d`、`drafted_count`、`accepted_count`、pseudo cache size 等字段。这说明后面做在线 controller 的工程路径是通的。

第二，**controlled lookup 下 acceptance 很高，尤其 d=3。**

你给的结果里，d=3 的 J 值在所有 workload 上最小：

```text
chat_low:    d=3 J=6.334
chat:        d=3 J=6.721
code:        d=3 J=4.335
rag:         d=3 J=4.843
structured:  d=3 J=5.528
```

这意味着当前 controlled lookup workload 下，`fixed d=3` 很强，不是弱 baseline。

第三，**per-step trace 证明 workload acceptance 确实有差异，但还不足以证明 adaptive controller。**

d=3 下的实际 acceptance per draft token：

```text
chat:       0.503
chat_low:   0.554
code:       0.961
rag:        0.825
structured: 0.682
```

这个说明 workload 有差异，但因为只测了 d=3 的 per-step trace，不能回答：

```text
同一个 step 上，如果选 d=0/1/3/7，哪个最好？
```

也就不能 replay oracle、EWMA controller、goodput-only controller。

---

## 2. 为什么 d=3 会这么强？

这不是反常，反而是 R8T4 curve-shaping 成功后的自然结果。

你现在的 T=4 verifier cost 非常低：

```text
C_verify(4) / C_verify(1) ≈ 1.399
```

如果 d=3，即 T=4，投机划算条件近似是：

```text
[C_verify(4) + C_draft(3)] / [1 + E_accept(3)] < C_verify(1)
```

忽略很小的 draft cost，大约需要：

```text
E_accept(3) > 0.399
```

也就是说，只要平均接受超过 0.4 个 draft token，d=3 就可能比 no-spec 划算。

你们 controlled lookup 下即使 chat 也远高于这个门槛，所以 d=3 全部 workload 最优是合理的。这说明：

```text
R8T4 把 speculation 的 break-even 门槛压得很低。
```

这对 kernel/system 主线是强证据；但对“adaptive controller 必须存在”这个 claim 是挑战，因为 fixed d=3 可能已经足够好。

---

## 3. 现在不能宣布 FULL SYSTEM GO 的原因

目前还缺一个关键证据：

> **在同一个运行位置上，d=0/1/3/7 的候选结果是什么？**

现在有两种数据：

```text
aggregate sweep:
  每个 workload 分别跑 d=1/3/7，得到平均 E 和 J。

per-step trace:
  只跑 d=3，得到每一步 accepted_count。
```

但 controller / oracle 需要的是：

```text
for each same pseudo/runtime position:
  accepted_count(d=0)
  accepted_count(d=1)
  accepted_count(d=3)
  accepted_count(d=7)
```

没有这个 aligned candidate trace，就无法严格比较：

```text
fixed d=3
offline oracle
EWMA online controller
goodput-only adaptive
VeriCurve controller
```

所以当前状态应该写成：

```text
trace plumbing: GO
controlled acceptance: GO
controller contribution: NOT PROVEN
FULL SYSTEM GO: NO
```

---

## 4. 现在最关键的下一步

下一步不要继续优化 kernel，也不要继续改 paper framing。现在唯一关键是：

# **做 candidate-aligned lookup trace 或 runtime choose_d。**

也就是从：

```text
每个 workload 分别跑 d=1/3/7
```

升级到：

```text
同一个 step 上同时评估 d=0/1/3/7
```

这样才能 replay：

```text
oracle
fixed d
EWMA controller
goodput-only controller
VeriCurve controller
```

---

# 给 agent 的下一轮任务

建议新开或继续当前 Trellis task，但把目标改成：

```text
candidate-aligned-controller-replay
```

目标：

```text
Determine whether VeriCurve-RV online/adaptive control can beat fixed d=3
using aligned per-step candidate evidence from the same pseudo/runtime positions.
```

---

## Task 1：构建 candidate-aligned lookup trace

当前 d=3 trace 不够。需要在同一个 pseudo position 上评估：

```text
d ∈ {0, 1, 3, 7}
```

每一步记录：

```text
workload_id
prompt_id
step_id
pseudo_position
pseudo_state_hash_before
target_token_position
candidate_d
drafted_count(d)
accepted_count(d)
draft_tokens(d)
target_tokens_for_compare
pseudo_state_hash_after_if_committed
```

关键要求：

```text
不同 d 必须来自同一个 pseudo_state_before。
不能 d=1 跑一遍、d=3 跑另一遍后直接平均比较。
```

如果 lookup-stats 内部状态难以 clone，可以用 replay 方式：

1. 先固定一条 target token 序列；
2. 对每个 position 构建同一个 pseudo lookup state；
3. 对 d=1/3/7 分别查询 draft；
4. 和同一条 target continuation 比较 accepted_count。

产物：

```text
results/aligned_candidate_trace.csv
research/aligned_candidate_trace.md
patches/aligned_candidate_trace.patch
```

Go/No-Go：

```text
GO:
  每个 workload 至少有 100 个 aligned steps；
  每个 step 上 d=0/1/3/7 都有 accepted_count；
  d=3 aggregate 能复现上一轮 d=3 trace ±5~10%。

CONDITIONAL:
  能 aligned，但 step 数少或复现误差较大。

NO-GO:
  无法从同一 pseudo position 评估多个 d。
```

---

## Task 2：用 aligned trace 做 offline replay

用统一成本表：

```text
C_verify(T)
C_draft(d)
```

对 aligned trace replay：

```text
B0 no speculation
B1 fixed d=1
B2 fixed d=3
B3 fixed d=7
B4 offline-best fixed d over mixed workload
B5 offline-best fixed d per workload
B6 goodput-only adaptive
B7 VeriCurve-EWMA replay
B8 oracle per step
```

注意 oracle 必须按：

```text
total cost / total emitted tokens
```

而不是平均每个 step 的 `cost/tokens`。你们 spec 里已经补了这个口径，这是对的。

产物：

```text
results/aligned_replay_summary.csv
research/aligned_replay_summary.md
scripts/replay_aligned_controller.py
```

Go/No-Go：

```text
FULL SYSTEM GO:
  VeriCurve replay beats fixed d=3 by >= 8%
  and reaches >= 90% oracle
  and does not regress low-acceptance workload by >3%.

CONDITIONAL:
  VeriCurve beats default/no-spec and mixed fixed,
  but fixed d=3 remains within 3~5%.

NO-GO controller:
  fixed d=3 is within 3% of oracle across mixed workload.
```

---

## Task 3：构造真正低接受 workload

现在 `chat_low` 其实不够低。原因很可能是 prompt lookup 被 `User/Assistant` 模板、重复格式、短 token pattern 抬高了 acceptance。

下一轮必须加入更“反 lookup”的 workload：

```text
raw_chat_no_template
high_entropy_qa
creative_writing
random_topic_switch
multi-turn with deliberately changing topic
temperature > 0 sampling trace if feasible
```

同时保留高接受 workload：

```text
code refactor
structured JSON
RAG template
repeated boilerplate
```

目标是制造 acceptance drift：

```text
low acceptance workload: best d = 0 or 1
high acceptance workload: best d = 3 or 7
```

产物：

```text
research/workload_hardening.md
results/aligned_candidate_trace_hardened.csv
```

Go/No-Go：

```text
GO:
  至少一个 workload 的 best d 是 0/1；
  至少一个 workload 的 best d 是 3/7。

NO-GO:
  d=3 仍然在所有 workload 上接近 oracle。
```

如果这个 NO-GO 出现，不代表项目死了；只是说明 controller 应该降级，fixed d=3 就是推荐策略。

---

## Task 4：integrated path cost validation

现在 controlled lookup 还要确认真正 integrated path 里：

```text
T=4 是否真的用 R8T4/R8 verifier
T=1/2 是否真的用 old vecdot
```

记录：

```text
selected_T
selected_verifier_variant
C_verify_integrated(T)
C_draft_integrated(d)
accepted_count
total_step_latency
```

产物：

```text
results/integrated_variant_trace.csv
research/integrated_variant_trace.md
```

Go/No-Go：

```text
GO:
  integrated C_verify(4)/C_verify(1) <= 1.8
  and T=4 selects R8T4/R8 path.

CONDITIONAL:
  integrated ratio <= 2.5.

NO-GO:
  integrated path loses curve shaping or cannot call R8T4.
```

这个非常关键。如果 microbench 曲线无法进入真实 llama.cpp path，系统论文会退化成 kernel paper。

---

## Task 5：只有 replay GO 后再做 online EWMA

如果 aligned replay 证明 controller 能赢 fixed d=3，再做真实 online controller。

配置：

```text
d candidates = {0,1,3,7}
EWMA alpha = 0.2 or 0.3
window = 8 or 16 tokens
switch margin = 5%
minimum dwell = 2 windows
```

记录：

```text
step_id
selected_d
estimated_acceptance
actual_acceptance
estimated_J(d)
actual_J(d)
switch_reason
emitted_tokens
step_cost
```

产物：

```text
results/online_ewma_controller.csv
research/online_ewma_controller.md
patches/online_ewma_controller.patch
```

Go/No-Go：

```text
FULL SYSTEM GO:
  online VeriCurve beats fixed d=3 by >=8%
  and reaches >=90% oracle replay
  and overhead <1%.

CONDITIONAL:
  online VeriCurve wins some mixed workloads but not fixed d=3.

NO-GO:
  online controller adds overhead/noise and fixed d=3 remains best.
```

---

# 如果 fixed d=3 一直赢，怎么办？

这不是整个方向失败。它只是说明：

```text
adaptive controller 不是主贡献。
```

那最终 paper 应该改成：

# **VeriCurve-RV: Curve-Shaped Verification for RISC-V Speculative Inference**

而不是强调 controller。

核心贡献变成：

```text
1. 发现 old llama.cpp/RVV verifier curve 近似线性；
2. direct R1T4 失败，说明 T visibility 不够；
3. R8T4 RTile×TTile verifier 把 C(4) 压到 1.399×T1；
4. 这个新 curve 让 fixed d=3 lookup speculation 在多种 workload 上变得有效；
5. controller 是可选增强，但不是必要条件。
```

这种 paper 仍然可以成立，只是从：

```text
adaptive speculation controller paper
```

变成：

```text
curve-shaping verifier kernel + speculation enablement paper
```

这可能反而更稳，因为你现在最强的实验证据就是 R8T4 curve shaping，而不是 online controller。

---

# 当前最终判断

我会把当前状态写成：

```text
VeriCurve-RV: continue
curve-shaping kernel: strong evidence
fixed d=3 policy: currently very strong
adaptive controller: not yet proven
next decisive test: aligned candidate replay
```

所以，是的，**还需要继续确认下一步怎么做**，但不是发散式继续，而是只做一个核心判断：

> **在同一 runtime/pseudo position 上，d=0/1/3/7 的结果是否足够不同，使 VeriCurve controller 能超过 fixed d=3？**

如果能，继续 full system controller。
如果不能，立刻把最终论文主线收敛为：

> **RTile × TTile verifier curve shaping enables efficient speculative verification on RISC-V; fixed d=3 is the recommended simple policy under lookup-style workloads.**

这会让论文更稳，不会为了追 controller 而硬拗。
