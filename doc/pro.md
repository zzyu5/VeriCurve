你现在这个结果**非常有价值**，而且它把方向从“概念讨论”推进到了一个真实 Go/No-Go 节点。

我的判断是：

> **当前不是 full system GO，但已经是明确的 kernel-gap GO。**
>
> 也就是说：
> **旧 llama.cpp/RVV 路径在你测的 Q4_0 prompt-pass T=1/2/4/8/16 上几乎线性增长，说明现有路径没有有效利用 token-width / multi-RHS amortization。下一步应该立刻进入 minimal T4 verifier kernel，而不是继续讨论 scheduler/controller。**

你现在的结果：

```text
T=1   total_ratio=1.000  per_token_ratio=1.000
T=2   total_ratio=1.965  per_token_ratio=0.983
T=4   total_ratio=3.926  per_token_ratio=0.982
T=8   total_ratio=7.753  per_token_ratio=0.969
T=16  total_ratio=15.561 per_token_ratio=0.973
```

这说明当前路径基本是：

```text
T 个 token ≈ T 次 T=1
```

也就是 **old verifier curve 近似线性**。这对“只做 adaptive speculation controller”其实是坏消息，因为旧曲线下 controller 最优选择大概率是不投机；但对 **VeriCurve-RV** 是好消息，因为它证明了一个具体 gap：

> **如果我们能做出 T=4 / T=8 multi-RHS verifier kernel，把 C(4) 从约 4× 压到 2× 左右，那么 speculative verification 的成本结构才会真正改变。**

---

## 1. 当前结果对最终 idea 的影响

我现在会把最终 idea 再压得更实一点：

# **VeriCurve-RV：Curve-Shaping Verifier Kernels + Curve-Aware Speculation**

中文：

> **VeriCurve-RV：面向 RISC-V LLM 推理的验证成本曲线塑形与投机策略协同设计**

注意重点变化：
不要说成“我们做一个 kernel-centric scheduler”。这个太宽，容易被 TurboSpec / Sequoia / DISCO / vLLM scheduler 打。你和 Claude 的讨论也已经指出，FrontierFill 原样会被已有 adaptive speculation 工作威胁。

也不要说成“我们只做 cache-aware controller”。你现在的旧曲线几乎线性，说明当前路径下 cache / batch 自然摊薄并没有显著发生；如果不改 verifier kernel，controller 大概率没有东西可利用。

最准确的主张应该是：

> **在 RISC-V/RVV low-bit LLM 推理中，旧 verifier path 的 `C_verify(T)` 近似线性，使 speculative verification 缺少物理收益基础。VeriCurve-RV 先通过 T-specialized multi-RHS verifier microkernels 重塑 `C_verify(T)` 曲线，再让 llama.cpp runtime 根据新曲线、draft cost 和 acceptance rate 决定是否投机、投机到哪个 T。**

这比“kernel-centered scheduler”更强，因为它不是简单调度，而是：

```text
microkernel design 改变 C_verify(T)
        ↓
C_verify(T) 改变 speculation cost model
        ↓
runtime 决策随之改变
```

---

## 2. 现在已经可以判定什么？

### 已经可以 GO 的部分

**GO-1：RISC-V/RVV 当前旧路径确实缺少明显 T 方向 amortization。**

你测到 `T=4` 约等于 `3.926×T=1`，`T=8` 约等于 `7.753×T=1`。这已经足够说明：在这个配置下，当前 llama.cpp/RVV path 不像一个有效的 multi-RHS verifier。

**GO-2：继续做 characterization 是值得的。**

现在不是 No-Go，而是应该把当前任务结论升级为：

```text
GO-kernel-gap
CONDITIONAL-system
```

这个判断是对的。

**GO-3：下一步应该做 minimal T4 verifier kernel。**

不要先做 controller，不要先做 agent，不要先搞复杂 system。先证明：

```text
C_new(4) << C_old(4)
```

或者至少：

```text
C_new(4) / C_old(4) <= 0.7
```

否则系统论文没有物理基础。

---

## 3. 现在还不能判定什么？

### 不能判定 full system GO

因为还没有：

```text
C_new(T)
C_draft(d)
acceptance(d)
mixed workload drift
end-to-end speculative throughput
```

所以现在不能说“VeriCurve-RV full system 一定成立”。

### 不能判定 controller 有价值

旧曲线线性时，controller 选择不投机是数学上很自然的事情，不是研究贡献。真正的 controller 价值必须在新 kernel 后证明：

```text
new C_verify(T) 有甜区 / 曲线漂移
+
acceptance rate 在 workload 间漂移
+
固定 draft length 会系统性误选
+
curve-aware controller 接近 oracle
```

### 不能把当前 prompt-pass 曲线完全等同于 verifier microkernel 曲线

你现在测的是 Q4_0 prompt-pass `C_old(T)`，很有信号价值，但下一步必须拆到更低层：

```text
当前 T=4 到底走了哪些 ggml / RVV 函数？
是否是 T 次 vec_dot？
是否进了 repack 16x1 path？
是否有 tinyBLAS / llamafile path？
```

否则 reviewer 会问：你测的是完整 prompt pass，怎么证明瓶颈就是 q4/q8 verifier kernel？

---

## 4. 最终 idea 应该怎么写

我建议最终论文定位为：

> **VeriCurve-RV studies how RISC-V/RVV low-bit verifier cost curves are shaped by microkernel design, and how these curves should drive speculative decoding decisions.**

中文：

> **VeriCurve-RV 研究 RISC-V/RVV low-bit verifier 的成本曲线如何被 microkernel 设计塑形，以及这条曲线如何进入 speculative decoding 决策。**

贡献不要写成四个大而全的东西，而是压成：

```text
C1. Characterization:
    表征当前 llama.cpp/RVV old verifier curve 近似线性，
    并定位 token-width 没有被有效利用的 kernel path。

C2. Curve-shaping microkernel:
    实现最小 T4/T8 multi-RHS RVV verifier kernel，
    证明 C_verify(T) 可以被 microkernel design 改变。

C3. Curve model:
    用轻量模型解释 C_verify(T) 的甜区和漂移：
    weight/dequant reuse, VLEN/LMUL, accumulator pressure, cache/memory。

C4. Curve-aware speculation:
    在 llama.cpp speculative decoding 中根据
    C_verify(T), C_draft(d), acceptance(d)
    选择 draft budget，并对比 fixed/oracle/goodput-only。
```

IntentIR / TianchenRV 可以作为博士主线背景，不要作为单篇论文硬依赖。IntentIR 已经证明 schedule choices 可以作为 non-binding hints 被后端 retune，并在 RVV 上有 retuning 和 explicit RVV lowering 的收益；这个给博士叙事提供了支撑，但这篇第三课题最好单篇自包含。

---

# 给 agent 的下一步 Go/No-Go 指令

下面这段可以直接丢给 agent。

---

## 新 Trellis 任务

创建新任务：

```text
.trellis/tasks/06-16-minimal-t4-verifier-kernel/
```

任务名：

```text
minimal-t4-verifier-kernel
```

任务结论目标：

```text
Decide whether a T-specialized RVV verifier microkernel can reshape
C_verify(T) enough to justify VeriCurve-RV system work.
```

不要归档当前 go-nogo 任务。当前任务保留为 upstream evidence。

---

## Task 0：整理当前结论

在新任务的 `prd.md` 开头写清楚：

```text
Previous task result:
  GO-kernel-gap / CONDITIONAL-system

Evidence:
  C_old_prompt_T on ssh rvv, Q4_0, threads=1:
    T=1  ratio=1.000
    T=2  ratio=1.965
    T=4  ratio=3.926
    T=8  ratio=7.753
    T=16 ratio=15.561

Interpretation:
  Current old path is repeated-T1-like.
  It does not yet prove full VeriCurve-RV system GO.
  Next task must prove or refute C_new(4) curve shaping.
```

---

## Task 1：Trace current llama.cpp/RVV path

目标不是再跑 benchmark，而是回答：

```text
T=1,2,4,8 时，真实调用了什么 kernel path？
```

必须区分：

```text
ggml_vec_dot_*_q8_*             single-RHS vec-dot path
ggml_gemv_*_16x1_*              repack GEMV path
ggml_gemm_*_16x1_*              repack GEMM path
llamafile / tinyBLAS path
fallback scalar path
```

建议 agent 做最小 trace：

```text
GGML_VERICURVE_TRACE=1
```

trace 输出不要每次循环都打印，避免扰动性能。只计数：

```text
function_name
call_count
n / nc / nr / nrc / bs
T or token_width if available
total_time_ns if cheap
```

产物：

```text
research/current_path_trace_T1_T2_T4_T8.md
artifacts/current_path_trace.csv
```

### Task 1 Go/No-Go

**GO-T4-kernel**：

```text
T>1 时 q4/q8 low-bit path call_count 近似随 T 线性增长，
或者 trace 显示底层仍是 nrc==1 / single-RHS vec-dot 风格。
```

**CONDITIONAL**：

```text
存在 repack/GEMM path，但 C_old(T) 仍然近线性。
继续做 microbenchmark，确认瓶颈是否在该 path。
```

**NO-GO for T4 kernel**：

```text
trace 显示当前已经使用高效 multi-RHS low-bit GEMM，
且 microbenchmark C_old(4) < 2.2*C_old(1)。
```

目前根据你已有数据，预计会是 GO 或 CONDITIONAL，不太可能直接 No-Go。

---

## Task 2：做 ggml-level C_old(T) microbenchmark

不要只依赖完整 llama-bench。写一个更小的 harness：

```text
bench_qmatmul_T.cpp
```

它要直接测 low-bit qmatmul / dot 路径：

```text
T = 1, 2, 4, 8, 16
quant = first target Q4_0 × Q8_0
threads = 1
same model-like hidden size / row count
warmup + repeat
```

输出：

```text
C_old_qmatmul(T)
C_old_qmatmul(T)/C_old_qmatmul(1)
per_token_latency
trace path
```

产物：

```text
research/C_old_qmatmul_T_threads1.md
artifacts/C_old_qmatmul_T_threads1.csv
```

### Task 2 Go/No-Go

**GO-T4-kernel**：

```text
C_old_qmatmul(4) >= 3.4 * C_old_qmatmul(1)
```

说明旧低层 kernel 基本没有 T amortization。

**CONDITIONAL**：

```text
2.4 * C_old(1) <= C_old(4) < 3.4 * C_old(1)
```

说明已有部分 amortization，但仍可能有 T4 kernel 空间。

**NO-GO for low-bit T4 gap**：

```text
C_old(4) < 2.2 * C_old(1)
```

说明当前低层路径已经有强 multi-RHS amortization。此时不要继续写 T4 kernel，转向 controller / C_draft / acceptance characterization。

---

## Task 3：实现最小 T4 verifier microkernel

先不要覆盖所有 quant。选最容易、最干净的一条：

```text
Q4_0 × Q8_0
```

最小目标：

```text
T4 microkernel:
  one weight row/block
  four RHS activation vectors
  four accumulators
  weight block load/decode once
  output four scalar results
```

不要一开始追求完整 llama.cpp integration。先 microbenchmark 和 correctness。

输出 API 可以先是内部 harness 级别：

```c
void q4_0_q8_0_dot_t4_rvv(
    int n,
    float out[4],
    const block_q4_0 * x,
    const block_q8_0 * y0,
    const block_q8_0 * y1,
    const block_q8_0 * y2,
    const block_q8_0 * y3
);
```

正确性对比：

```text
4 × existing ggml_vec_dot_q4_0_q8_0
```

性能对比：

```text
C_new_t4
vs
C_old_t4 = 4 × existing T1 path
vs
C_old_prompt_T4 if applicable
```

产物：

```text
research/t4_kernel_design.md
research/C_new_T4_microbench.md
artifacts/C_new_T4_microbench.csv
patches/t4_kernel_minimal.patch
```

### Task 3 Go/No-Go

**STRONG GO-system**：

```text
C_new(4) <= 2.2 * C_old(1)
and
C_new(4) <= 0.60 * C_old(4)
correctness passes
```

这说明 T4 kernel 真正 reshape 了 verifier curve。

**GO-system**：

```text
C_new(4) <= 2.6 * C_old(1)
and
C_new(4) <= 0.70 * C_old(4)
correctness passes
```

可以继续做 T2/T8 和 controller。

**CONDITIONAL**：

```text
C_new(4) <= 3.2 * C_old(1)
or
C_new(4) <= 0.85 * C_old(4)
```

说明有收益但不足。下一步只允许做一次优化 pass，例如改 LMUL / accumulator layout / unroll；如果仍不足，降级为 kernel paper 或换 path。

**NO-GO for VeriCurve system**：

```text
C_new(4) > 3.2 * C_old(1)
and
C_new(4) > 0.85 * C_old(4)
```

说明 T4 microkernel 没能改变曲线。不要做 controller。

---

## Task 4：扩展 T2/T8，找甜区和漂移

只有 Task 3 GO 后才做。

实现或模拟：

```text
T2
T4
T8
```

测：

```text
C_new(1), C_new(2), C_new(4), C_new(8), C_new(16)
```

如果 T8 实现成本高，可以先测 T2/T4。

产物：

```text
research/C_new_curve_T1_T2_T4_T8.md
artifacts/C_new_curve.csv
```

### Task 4 Go/No-Go

**GO-controller**：

```text
存在非平凡选择：
  best T differs across quant/model/hardware
  or best T differs under expected acceptance levels
  or T8 shows register/cache pressure rebound
```

**CONDITIONAL-controller**：

```text
T4 dominates T1/T2/T8 on all cases.
```

这种情况下 controller 价值变弱，但仍可做 “fixed T4 speculation” 或 minimal controller。

**NO-GO-controller**：

```text
所有 T>1 收益都弱，或一个 static policy 接近 oracle。
```

不要继续做 adaptive controller。

---

## Task 5：测 C_draft(d) 和 acceptance

只有 Task 3 至少 GO 后做。

先测 cheap draft，不要先上小 draft model：

```text
ngram-simple
ngram-map
ngram-mod
```

再可选：

```text
small draft model
```

workload 必须包括：

```text
chat / random Q&A          low acceptance negative case
code completion/refactor   high ngram acceptance
RAG/template               medium/high structured case
structured output          format repetition case
```

测：

```text
C_draft(d)
E_accept(d)
d ∈ {1,3,7,15}
```

产物：

```text
research/C_draft_acceptance.md
artifacts/draft_acceptance.csv
```

### Task 5 Go/No-Go

**GO-controller**：

```text
存在至少两个 workload，其 optimal d 不同；
并且新 C_verify(T) 下某些 workload 的 predicted speedup >= 1.15×。
```

**CONDITIONAL**：

```text
只有一个 workload 有收益，或 predicted speedup 1.05×~1.15×。
```

可以做小系统，但论文主 claim 要弱化。

**NO-GO**：

```text
ngram acceptance 低，draft model cost 高，
所有 d 的 J(d) 都不优于 d=0。
```

此时 speculative controller 不成立；保留 kernel characterization / low-bit microkernel 方向。

---

## Task 6：最小 curve-aware controller

只有 Task 5 GO 后做。

公式：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
d ∈ {0,1,3,7,15}
```

运行时策略：

```text
加载 profile table
每 8 或 16 个生成 token 更新 acceptance estimate
查表选择 d
```

不要做 RL，不要做 agent，不要做复杂在线 tuning。

baseline：

```text
B0 no speculation
B1 llama.cpp default fixed speculation
B2 offline-best fixed d per workload
B3 offline-best fixed d over mixed workload
B4 goodput-only adaptive
B5 VeriCurve-RV
B6 oracle
```

### Task 6 Go/No-Go

**FULL SYSTEM GO**：

```text
VeriCurve-RV beats offline-best fixed d over mixed workload by >= 10%
and reaches >= 90% oracle
and has no major regression on low-acceptance workload.
```

**CONDITIONAL PAPER GO**：

```text
VeriCurve-RV beats default/fixed but not offline-best fixed d.
```

这可以写 workshop / short paper，但强会论文风险较高。

**NO-GO SYSTEM**：

```text
offline-best fixed d matches oracle within 3~5%，
or goodput-only adaptive matches VeriCurve-RV.
```

说明 controller 不新，回退到 characterization + microkernel paper。

---

# 额外提醒 agent 的几个硬规则

### 不要继续做 broad scheduler

当前旧曲线线性已经说明：
**没有新 verifier curve，scheduler 没东西可利用。**

所以不要先做：

```text
kernel-centric scheduler
profile-driven scheduler
agent controller
general framework
```

先做 T4 kernel。

### 不要强绑定 TianchenRV

单篇论文先自包含。
可以写：

```text
The minimal kernel is handwritten or small generated.
TianchenRV integration is future/extended implementation.
```

博士大论文里再把它串起来。IntentIR 论文里三层分离和 RVV retuning 是主题背景，但这篇第三课题不要依赖它才能成立。

### 不要只看 prompt-pass

当前 `C_old_prompt_T` 是强信号，但下一步必须有：

```text
ggml-level qmatmul microbench
trace path
event/counter if available
```

否则容易被 reviewer 质疑“你测的是整模型，不是 verifier kernel”。

### 不要忘记 C_draft

CPU/RVV 上 draft cost 是 critical path。
没有 `C_draft(d)`，controller 公式不完整。

---

# 最终对当前状态的判定

你现在已经完成了第一道关键门槛：

```text
old C(T) near-linear → kernel gap exists
```

所以现在的 Go/No-Go 状态应该写成：

```text
GO-kernel-gap
GO-minimal-T4-kernel
CONDITIONAL-controller
CONDITIONAL-full-system
```

下一步唯一正确动作：

> **开 minimal-t4-verifier-kernel task，先 trace 当前 path，再做 ggml-level C_old(T)，再做最小 T4 microkernel。**

如果 T4 microkernel 能把 `C(4)` 从约 `4×C(1)` 压到 `2~2.5×C(1)`，VeriCurve-RV 就进入真正的 system track。
如果压不下来，不要硬做 controller，直接 No-Go 这个系统方向。
