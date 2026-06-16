这轮结果其实比上一轮更好，因为它纠正了一个非常关键的方法学错误：

aggregate sweep 不能证明 controller，因为不同 d 的 run 走的是不同 pseudo-output trajectory。必须做 candidate-aligned counterfactual trace。

现在 aligned trace 做出来以后，局面变成：

VeriCurve-RV 主线：继续
curve-shaping kernel：已经很强
controller opportunity：重新出现
full system：仍然没过
下一步：不是再测 aggregate，也不是立刻写 online controller，而是先把 replay 做成 selected-only / commit-aware / train-test 的可靠版本

上一轮已经确认 R8T4 是 STRONG GO：direct R1T4 失败，但 row-blocked R8T4 成功，T=4 verifier 从 48.085 ms 压到 16.826 ms，相对 old T4 是 2.858×，并且 C_candidate_T4_total / C_best_T1 = 1.399；同一文件还说明 T=1/2 由 old vec-dot 胜，T=4/8 由 R8 no-pack 胜，说明 runtime variant crossover 是真实的。

1. 这轮最重要的结论

你现在有了一个非常强的修正：

aggregate sweep 看到 d=3 全 workload 最优
aligned replay 看到：
  chat/chat_low: d=0 比 d=3 好
  code/rag/structured: d=3 最好

这说明 controller 的基本前提重新成立了：

不同 workload / 不同 step 上的最优 d 不是固定值。

更重要的是，你们证明了 fixed d=3 不是 oracle：

no speculation:                 12.024 ms/token
fixed d=3:                      10.248 ms/token
best fixed per workload:         8.914 ms/token
VeriCurve EWMA full-info replay: 9.035 ms/token
oracle:                          7.666 ms/token

这几个数的含义是：

fixed d=3 比 no-spec 快，但不是最优；
VeriCurve full-info replay 比 fixed d=3 成本低约 11.8%；
goodput-only 选 d=7 直接崩掉，说明“只看 goodput/acceptance、不看 verifier curve”会过度投机；
但是 VeriCurve full-info replay 只达到 oracle 的 84.9%，还没有 full-system GO。

所以这一轮的真实状态应该写成：

aligned candidate trace: GO
workload-dependent policy opportunity: GO
curve-aware controller: CONDITIONAL GO
selected-only online controller: NOT PROVEN
FULL SYSTEM GO: NO
2. 当前最大的风险

现在不是 kernel 风险，而是 controller 证明风险。

你们现在的 VeriCurve EWMA full-info replay = 9.035 ms/token 是一个很有用的中间结果，但它有两个问题。

第一，它是 full-info replay。也就是说，它在 replay 时拥有所有 candidate d 的 aligned counterfactual 信息。真实 online controller 只能看到自己选择的 d 的实际接受数，除非主动 exploration。

第二，它只达到 oracle 的 84.9%。如果 full-info EWMA 都只有 84.9%，那一个 selected-only online EWMA 通常不会自然涨到 90%。所以下一步不应该直接写 runtime choose_d，然后期待它过线。你应该先在 aligned trace 上回答：

为什么 full-info EWMA 离 oracle 还有 15.1% gap？
gap 是来自：
  1. policy 太笨？
  2. candidate d 集合不够？
  3. cost table 不准？
  4. replay 不 commit-aware？
  5. oracle 本身利用了不可在线获得的信息？

这一步做清楚之前，直接进入 online controller 会很可能浪费时间。

3. 下一步首先要确认 replay 是否正确

这是我最担心的技术点。

aligned trace 不是最终答案。关键是 replay 必须是 commit-aware。

也就是说，policy 在某个 position 选择 d=3，如果 accepted_count=2，那么它不是“下一行继续 replay”，而是应该：

emitted = 1 + accepted_count = 3 tokens
next_position += 3

如果 replay 只是对所有 aligned steps 逐行求 cost / emitted_tokens，那 oracle、fixed d、EWMA 的数都会偏。你们之前已经意识到 oracle 必须按 total cost / total emitted tokens 算，这是对的；但还要再确认 position advancement / skipping 是否也正确。

所以我建议下一轮第一个任务不是写 online controller，而是：

validate replay semantics:
  selected d -> accepted_count -> advance pseudo_position

如果现有 replay 已经这样做了，就在报告里明确写出来。如果没有，先修。

4. 给 agent 的下一轮任务

下面这段可以直接给 agent。

新任务名

继续当前 task 也可以，但建议开一个更明确的 subtask：

06-16-selected-only-controller-replay

目标：

Turn aligned full-info replay into a commit-aware, selected-only controller replay.
Decide whether VeriCurve controller can beat fixed d=3 under realistic observability.
Task 1：Replay correctness audit

先审计 replay_aligned_controller.py。

必须回答：

1. replay 是否按 selected d 的 accepted_count 跳过后续 positions？
2. oracle 是否也是 commit-aware oracle？
3. fixed d=3 是否用同样的 commit/skip 规则？
4. total cost / total emitted tokens 是否是全局聚合，而不是 per-step 平均？
5. d=0 的 emitted token 是否正确记为 1？
6. d=7 失败是否来自真实 cost/emitted，而不是 replay bug？

产物：

research/replay_correctness_audit.md
results/replay_sanity_checks.csv

Go/No-Go：

GO:
  replay is commit-aware and all baselines use same semantics.

CONDITIONAL:
  replay is mostly correct but some workload alignment is approximate.

NO-GO:
  replay is not commit-aware.
  Then all controller numbers must be recomputed.
Task 2：Oracle gap decomposition

现在最重要的是解释：

VeriCurve full-info = 9.035
oracle = 7.666
gap = 15.1%

让 agent 做 per-workload / per-step regret 分解：

for each workload:
  fixed d=3 cost
  full-info EWMA cost
  oracle cost
  oracle d distribution
  EWMA chosen d distribution
  regret by chosen d
  regret caused by choosing d=7
  regret caused by staying d=0 too long
  regret caused by missing d=3

产物：

results/oracle_gap_breakdown.csv
research/oracle_gap_breakdown.md

必须输出：

oracle_choice_distribution:
  chat/chat_low/code/rag/structured 分别多少 step 选 d=0/1/3/7

regret_hotspots:
  哪些 workload / 哪些 transition 贡献了主要 gap

这会告诉我们 controller 还能不能救。

Task 3：先做 better offline policies，不要直接 online

在 aligned trace 上评估几个非常简单但更强的 policy。

Policy A：two-action policy

因为目前 d=1、d=7 都不强，先只允许：

d ∈ {0, 3}

这会避免 goodput-only 那种过度选择 d=7 的灾难。

Policy B：threshold policy

根据最近 d=3 acceptance 估计：

if E_accept_3 > threshold:
    choose d=3
else:
    choose d=0

threshold 根据成本表计算：

threshold ≈ C_verify(4)/C_verify(1) - 1 + C_draft(3)/C_verify(1)

因为 R8T4 下 C_verify(4)/C_verify(1)≈1.399，所以 break-even 约是 0.4 + draft_cost_ratio。

Policy C：workload-label upper bound

先允许使用 workload label：

chat/chat_low -> d=0
code/rag/structured -> d=3

这个不是最终系统，但它是一个上界检查。它能回答：

如果我们能识别 workload type，最多能接近 oracle 到什么程度？
Policy D：selected-only bandit replay

只观察 selected d 的 reward，用 UCB/Thompson 或 epsilon-greedy 探索：

arms = {0,3} first
optional arms = {0,1,3,7}
reward = emitted_tokens / cost
minimum dwell = 8 steps
switch margin = 5%

产物：

results/policy_family_replay.csv
research/policy_family_replay.md
scripts/replay_policy_family.py

Go/No-Go：

STRONG:
  some realistic selected-only policy beats fixed d=3 by >=8%
  and reaches >=90% oracle.

GO:
  selected-only policy beats fixed d=3 by >=5%
  and reaches >=88% oracle.

CONDITIONAL:
  only workload-label or full-info policies beat fixed d=3.

NO-GO:
  fixed d=3 is within 3% of every realistic selected-only policy.
Task 4：train/test split，防止过拟合

现在的数据有 1556 aligned steps，可以做简单 split：

train prompts / chunks:
  tune thresholds, EWMA alpha, switch margin

test prompts / chunks:
  report final policy

不要在同一批 aligned trace 上既调参又报告最终数字。

产物：

results/policy_train_test.csv
research/policy_train_test.md

Go/No-Go：

GO:
  test result still beats fixed d=3 by >=5-8%.

NO-GO:
  train 好，test 掉光。
Task 5：再做 workload hardening

现在 chat 和 chat_low 的 aligned replay 已经显示 fixed d=0 更好，这是好事。但为了让论文更稳，继续加几个更低接受 workload：

raw_chat_no_template
high_entropy_qa
creative_writing
topic_switch_dialogue
temperature > 0 if feasible

目标不是让 controller 更好看，而是证明：

fixed d=3 并不普适；
在低接受 workload 上会退化；
curve-aware policy 能退回 d=0。

产物：

results/aligned_candidate_trace_hardened.csv
research/workload_hardening_v2.md
Task 6：只有 Task 3/4 GO 后，才做 runtime choose_d

如果 selected-only replay 过不了，就不要写 runtime choose_d。

如果过了，再实现最小 runtime controller：

d candidates = {0,3} first
optional {0,1,3,7}

EWMA alpha = tuned on train
window = 8 or 16
switch margin = 5%
minimum dwell = 2 windows

不要一开始做复杂 controller。

产物：

patches/runtime_choose_d.patch
results/runtime_controller_trace.csv
research/runtime_controller_result.md

Full-System Go/No-Go：

FULL SYSTEM GO:
  runtime controller beats fixed d=3 by >=8%
  and reaches >=90% oracle replay
  and overhead <1%
  and no regression on low-acceptance workload >3%.

CONDITIONAL:
  runtime controller beats fixed d=3 but <8%
  or reaches 85-90% oracle.

NO-GO:
  fixed d=3 remains within 3-5%.
5. 这轮结果如何影响论文定位？

现在有两种可能的最终论文。

路线 A：controller 过线

如果 selected-only / runtime controller 能明显赢 fixed d=3，那么论文就是：

VeriCurve-RV: Curve-Shaped Verification and Adaptive Speculation for RISC-V LLM Inference

贡献：

1. 发现 old RVV verifier curve 线性；
2. direct R1T4 失败；
3. R8T4 RTile×TTile reshape curve；
4. aligned candidate trace 证明 aggregate sweep 不可靠；
5. selected-only controller 根据 curve 和 observed acceptance 选择 d。
路线 B：controller 不过线

如果 fixed d=3 仍然接近最优，那么不要硬拗 controller。论文改成：

VeriCurve-RV: Curve-Shaped Verification for RISC-V Speculative Inference

贡献：

1. 发现 current llama.cpp/RVV verifier curve 线性；
2. 证明 T-visible direct kernel 不够；
3. 提出 RTile×TTile verifier microkernel，把 T=4 cost 压到 1.399×T1；
4. 证明这个新 curve 让 simple fixed d=3 lookup speculation 成为有效策略；
5. aligned trace 表明 controller 只有在 mixed/low-acceptance workload 下有潜在价值。

这条路线仍然能写，因为你最强的贡献其实是 curve-shaping verifier kernel，不是 controller。

6. 我的当前判断

我现在会把状态更新成：

VeriCurve-RV: 继续
Curve-shaping kernel: 已经成立
Aligned trace methodology: 已经成立，非常重要
Adaptive controller: 有机会，但尚未证明
Next decisive experiment: selected-only commit-aware replay

这轮最大的收获不是 EWMA=9.035，而是：

你们证明了 aggregate d sweep 是误导性的，必须做同一 pseudo/runtime position 上的 aligned candidate trace。aligned 后，fixed d=3 不再接近 oracle，controller opportunity 重新出现。

现在不要再做泛泛讨论。下一步就是：

1. 审计 replay 是否 commit-aware；
2. 做 oracle gap decomposition；
3. 在 aligned trace 上做 selected-only policy replay；
4. 只有 selected-only 过线，才写 runtime choose_d。

如果这一步过了，VeriCurve-RV full system 基本成立。
如果不过，也别硬做 controller，把论文收敛到 RTile×TTile curve-shaped verifier + fixed/spec policy analysis，仍然是一条很扎实的第三课题路线。

☆ 收藏