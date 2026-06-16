这轮的情况可以总结成一句话：

> **VeriCurve-RV 的 kernel 主线已经很强；controller 主线还没死，但现在被“trace coverage / replay semantics”卡住了。下一步不是继续跑 aggregate sweep，也不是马上写 online controller，而是先做 position-complete、commit-aware 的 selected-only replay。**

当前状态我会写成：

```text
Curve-shaping verifier kernel: STRONG GO
Schedule variant crossover: GO
Aligned candidate trace: GO
Controller opportunity: GO / CONDITIONAL
Selected-only online controller evidence: NOT YET
FULL SYSTEM GO: NO
```

你们上一轮已经确认，直接 R1T4 失败，但 row-blocked R8T4 成功：`C_candidate_T4_total = 16.826 ms`，相对旧 T4 是 `2.858×`，并且 `C_candidate_T4_total / C_best_T1 = 1.399`；同时 T=1/2 由 old vec-dot 最优，T=4/8 由 R8 path 最优，说明 variant crossover 是实测存在的。这个是 VeriCurve-RV 最强、最稳的核心证据。

---

## 1. 这轮到底发现了什么？

这轮最重要的不是 policy 数字，而是**方法学修正**。

上一轮 aggregate sweep 看起来：

```text
d=3 对所有 workload 都最好
```

但这一轮 candidate-aligned trace 说明：这个结论是误导性的，因为不同 d 的 run 走了不同 pseudo-output trajectory，不能直接比较。aligned 后真实情况变成：

```text
chat / chat_low:
  d=0 比 d=3 好

code / rag / structured:
  d=3 最好
```

所以 controller opportunity 重新出现了。固定 `d=3` 不再接近 oracle：

```text
fixed d=3:       10.248 ms/token
full-info EWMA:   9.035 ms/token
scan oracle:      7.666 ms/token
```

full-info EWMA 比 fixed d=3 好约 `11.8%`，说明“根据 acceptance / cost 曲线选择 d”确实有潜力。

但新的问题是：**这个 replay 还不是 selected-only / commit-aware replay。**

agent 已经发现旧 replay 的核心限制：

```text
旧 replay 是 recorded_position_scan
不是:
  next_position = current_position + 1 + accepted_count(selected_d)
```

而且当前 trace 是 committed `d=3` 轨迹上的 aligned counterfactual，所以它完整支持 d=3 replay：

```text
mixed d=3 missing next-position transitions: 0
```

但对非 d=3 selected path coverage 不足：

```text
mixed d=0 missing next-position transitions: 402
mixed d=1 missing next-position transitions: 318
```

高接受 workload 上尤其严重：

```text
code d=0 present fraction: 0.297
rag d=0 present fraction: 0.365
structured d=0 present fraction: 0.575
```

这意味着：如果一个真实 online controller 在某个位置选择 d=0，它下一步需要的 position 很可能没有出现在当前 d=3 committed trace 中。因此现在的 EWMA / threshold replay 仍然只能算 **scan-mode analysis**，不能作为真实 online controller 证据。

---

## 2. 这对论文方向意味着什么？

现在论文主线还是成立的，但重心要非常清楚：

### 已经比较稳的主线

```text
旧 llama.cpp/RVV verifier curve 近似线性
direct R1T4 不够
R8T4 RTile × TTile verifier reshapes C_verify(T)
reshaped curve makes speculation economically viable
```

这条线已经很强。

### 还没坐实的主线

```text
adaptive controller 明显优于 fixed d=3
selected-only online policy 接近 oracle
```

这条还没有坐实。

所以最终论文现在有两个可能形态。

**强系统版：**

> R8T4 curve shaping + selected-only online controller，显著胜过 fixed d=3 / goodput-only / oracle gap 小。

**稳健版：**

> R8T4 curve shaping + policy analysis，证明 reshaped verifier curve 让 fixed d=3 或 simple policy 在 lookup-style workload 上有效；adaptive controller 作为 secondary / future。

现在还不能决定走哪一个。下一轮就是为了决定这个。

---

## 3. 下一步最应该做什么？

我同意 agent 的判断：**优先 A，不要直接 B。**

也就是先做：

```text
A. position-complete aligned trace
```

而不是马上做：

```text
B. runtime choose_d()
```

但这里我会把 A 说得更严格一点：你们要的不是“再跑一个 d=0 trace”这么简单，而是要构造 **prefix-state-complete candidate trace**。

原因是 replay controller 时，policy 会不断跳到不同 position：

```text
position i
choose d
accepted a
next position = i + 1 + a
```

所以 trace 必须满足：

```text
对任何可能到达的 position i，
都有 d ∈ {0,1,3,7} 的 candidate result。
```

最稳的办法是：

> **用 d=0 / teacher-forced target prefix 生成每一个 target position 的 lookup state，然后在每个 position 上评估 d={0,1,3,7}。**

这样任何 policy 跳到哪个 target prefix，都能查到对应 candidate。
但这里有一个必须验证的前提：

```text
同一个 emitted prefix 是否产生同一个 lookup pseudo state，
不依赖它之前是通过 d=0 一步步生成，还是通过 d=3 一次接受多个 token 生成？
```

如果成立，d=0 teacher-forced trace 就可以作为 position-complete trace。
如果不成立，就需要 state cloning / runtime choose_d，不能用 teacher-forced trace。

---

# 4. 给 agent 的下一轮任务

下面这段可以直接给 agent。

---

## 新任务名

继续当前 task 也可以，但建议新开一个更明确的任务：

```text
06-16-position-complete-selected-replay
```

目标：

```text
Build a position-complete, commit-aware replay dataset and determine whether
a selected-only VeriCurve controller can beat fixed d=3.
```

---

## Task 1：确认 prefix-state equivalence

先不要跑大实验。先验证一个基础性质：

```text
同一个 emitted target prefix 下，lookup pseudo state 是否相同？
```

具体做法：

1. 选一小段 target token 序列。
2. 用 d=0 一步步推进到 position i，记录 pseudo_state_hash。
3. 用 d=3 接受若干 token 跳到同一个 position i，记录 pseudo_state_hash。
4. 比较 hash 或关键状态摘要。

需要记录：

```text
workload_id
position
path_type: d0_stepwise / d3_committed
pseudo_state_hash
pseudo_size
recent_tokens_hash
lookup_cache_hash if available
```

产物：

```text
research/prefix_state_equivalence.md
results/prefix_state_equivalence.csv
patches/pseudo_state_hash.patch
```

Go/No-Go：

```text
GO:
  same emitted prefix -> same pseudo state
  可以做 position-complete teacher-forced trace。

CONDITIONAL:
  pseudo state 有小差异，但 candidate accepted_count 基本一致。

NO-GO:
  同一 prefix 下 state 明显不同。
  不能用 teacher-forced trace，必须做 runtime choose_d 或 state cloning。
```

---

## Task 2：生成 position-complete aligned trace

如果 Task 1 GO，生成完整 trace：

```text
for every target position i:
  construct pseudo state from target prefix tokens[0:i]
  evaluate candidate d in {0,1,3,7}
  record accepted_count(d)
```

必须包含字段：

```text
workload_id
prompt_id
position
candidate_d
drafted_count
accepted_count
target_available
pseudo_state_hash
draft_update_us
```

产物：

```text
results/position_complete_candidate_trace.csv
research/position_complete_candidate_trace.md
```

质量 gate：

```text
GO:
  每个 workload 至少 100 positions
  每个 position 都有 d=0/1/3/7
  d=3 aggregate 与上一轮 committed d=3 trace 在 accepted_count 上误差 <= 5~10%

CONDITIONAL:
  coverage 够，但 d=3 复现误差 >10%

NO-GO:
  无法 position-complete
```

---

## Task 3：真正 commit-aware replay

用 position-complete trace 重写 replay：

```text
i = 0
while i < N:
  d = policy(state)
  a = accepted_count[i, d]
  cost += C_verify(1+d) + C_draft(d)
  emitted += 1 + a
  i += 1 + a
```

必须保证所有 baseline 用同一套 commit 语义：

```text
no speculation
fixed d=1
fixed d=3
fixed d=7
best fixed mixed
best fixed per workload
oracle
VeriCurve policies
goodput-only
```

产物：

```text
scripts/replay_commit_aware.py
results/commit_aware_replay_summary.csv
research/commit_aware_replay.md
```

Go/No-Go：

```text
GO:
  replay transition missing rate = 0
  fixed d=3 和 no-spec 结果合理复现
  oracle 按 total cost / total emitted tokens 计算

NO-GO:
  replay 仍然需要缺失 transition 插值。
```

---

## Task 4：先评估 two-action controller

现在不要急着用 `{0,1,3,7}`。
从结果看，主要决策其实是：

```text
chat/chat_low: d=0
code/rag/structured: d=3
```

而 d=7 很容易过度投机，goodput-only 已经因为选 d=7 崩了。

所以先做 arms：

```text
d ∈ {0, 3}
```

评估 policy：

### Policy A：fixed d=3

强 baseline。

### Policy B：workload-label upper bound

```text
chat/chat_low -> d=0
code/rag/structured -> d=3
```

不是最终算法，但可以告诉我们分类上界。

### Policy C：threshold selected-only

只观察 selected d 的结果，使用：

```text
if estimated_accept_d3 > threshold:
    d=3
else:
    d=0
```

threshold 可由成本公式给出：

```text
threshold ≈ C_verify(4) / C_verify(1) - 1 + C_draft(3)/C_verify(1)
```

R8T4 下大约是 0.4 左右。

### Policy D：periodic probe

因为 selected-only 如果一直 d=0，就永远不知道 d=3 是否变好，所以加：

```text
every 8 or 16 steps, force one d=3 probe
```

记录 probe overhead。

产物：

```text
results/two_action_policy_replay.csv
research/two_action_policy_replay.md
```

Go/No-Go：

```text
FULL CONTROLLER GO:
  selected-only two-action policy beats fixed d=3 by >= 8%
  and reaches >= 90% commit-aware oracle
  and no low-acceptance regression > 3%.

CONDITIONAL:
  beats fixed d=3 by 5%~8%
  or reaches 85%~90% oracle.

NO-GO:
  fixed d=3 within 3% of every selected-only policy.
```

---

## Task 5：再决定是否加入 d=1 / d=7

只有 `{0,3}` policy 过了之后，再考虑：

```text
d=1
d=7
```

加入规则：

```text
d=1 only for uncertain / moderate acceptance
d=7 only if d=3 acceptance is extremely high and C_verify(8) supports it
```

但不要让 d=7 一开始参与 unrestricted controller，因为目前 goodput-only 选 d=7 的结果非常差：

```text
goodput-only: 19.100 ms/token
```

---

## Task 6：train/test split

用 position-complete trace 做 train/test：

```text
train:
  tune threshold, alpha, probe interval, min samples

test:
  report final result
```

产物：

```text
results/commit_aware_train_test.csv
research/commit_aware_train_test.md
```

Go/No-Go：

```text
GO:
  test 仍然 beats fixed d=3 by >=5%~8%

NO-GO:
  train 有效，test 掉光
```

---

# 5. 当前应该如何判断项目？

我会把当前状态写成：

```text
VeriCurve-RV: continue
Curve-shaping kernel: STRONG GO
Aligned candidate method: GO
Scan-mode controller opportunity: GO
Commit-aware selected-only controller: BLOCKED_BY_TRACE_COVERAGE
FULL SYSTEM GO: NO
```

下一步只回答一个问题：

> **在 position-complete / commit-aware replay 下，selected-only two-action controller 能否赢 fixed d=3？**

如果答案是 yes，继续 runtime choose_d，full system 可能成立。
如果答案是 no，不要硬拗 controller，把论文收敛为：

> **RTile × TTile verifier curve shaping enables efficient fixed/speculative verification on RISC-V; adaptive control is workload-dependent and secondary.**

---

## 6. 最终论文现在有两个候选版本

### 版本 A：Controller 过线

题目：

> **VeriCurve-RV: Curve-Shaped Verification and Adaptive Speculation for RISC-V LLM Inference**

主贡献：

```text
R8T4 curve shaping
position-complete aligned replay
selected-only controller
end-to-end runtime choose_d
```

### 版本 B：Controller 不过线

题目：

> **VeriCurve-RV: Curve-Shaped Verification for RISC-V Speculative Inference**

主贡献：

```text
old RVV path linear
direct R1T4 no-go
R8T4 RTile × TTile curve shaping
fixed d=3 / simple policy becomes effective
aligned trace shows adaptive opportunity but fixed policy may suffice
```

版本 B 仍然能写，而且可能更稳，因为你们最强证据始终是 R8T4 把 curve 压下来了。

---

## 7. 我的最终建议

**继续，但不要扩大 scope。**

下一轮只做：

```text
prefix-state equivalence
position-complete aligned trace
commit-aware replay
selected-only {0,3} controller
```

不要做：

```text
更复杂 kernel
更多 d
agent controller
RL
完整 runtime integration
论文 framing
```

只有 commit-aware replay 过线，再做真正 runtime `choose_d()`。否则，controller 降级，论文主线回到 curve-shaping verifier kernel。
