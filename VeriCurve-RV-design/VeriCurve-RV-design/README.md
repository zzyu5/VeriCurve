# VeriCurve-RV: 面向 RISC-V LLM 推理的验证成本曲线与投机策略协同设计

> Working title: **VeriCurve-RV: Co-designing Verifier Cost Curves and Speculation Policies for RISC-V LLM Inference**

本文档是第三课题的系统设计总览。它把前面讨论过的 FrontierFill、KernelFlow、T-visible kernel、VeriKernel 等想法收敛成一个更可验证、更适合作为独立论文的系统：**VeriCurve-RV**。

---

## 0. 最终判断

第三课题不应该写成：

- “我们提出一个 kernel-centered inference framework”；
- “我们让 llama.cpp 更容易插入高性能 kernel”；
- “我们根据请求 shape 选择不同 kernel/block size”；
- “我们在 RISC-V 上复现 GPU adaptive speculation”；
- “我们只写一个更快的 multi-RHS RVV kernel”。

这些说法要么太泛，要么已有工作太多，要么会退化成第二课题的 kernel 优化。

第三课题应该写成：

> **在 RISC-V/RVV low-bit LLM 推理中，speculative decoding 的最优 draft budget 不是只由 acceptance rate 决定，而是由 verifier cost curve `C_verify(T)`、draft cost `C_draft(d)`、workload acceptance drift、RVV VLEN/LMUL/register pressure/cache behavior 共同决定。VeriCurve-RV 表征和建模这条曲线，用最小 T-specialized verifier kernels 重塑曲线，并在 llama.cpp 中用 curve-aware controller 选择 draft budget。**

其中：

```text
T = target verifier 一次同时验证的 token positions 数量

d = draft token 数

T = 1 + d
```

例如：

```text
no speculation: d = 0, T = 1
speculate 1 token: d = 1, T = 2
speculate 3 tokens: d = 3, T = 4
speculate 7 tokens: d = 7, T = 8
```

对每个 low-bit linear/verifier microkernel 来说，它对应：

```text
X[T, hidden] × W[hidden, out] -> Y[T, out]
```

权重 `W` 固定，模型结构固定；变化的是 verifier 一次处理几个 token positions，也就是 `T`。

---

## 1. 核心 thesis

### 1.1 一句话 thesis

> **VeriCurve-RV 研究 RISC-V/RVV low-bit speculative inference 中 verifier cost curve `C_verify(T)` 的形状、来源和使用方式。它证明：固定 draft length 在跨硬件、跨量化、跨 workload 的漂移下会系统性误选；而 curve-aware controller 能根据 `C_verify(T)`、`C_draft(d)` 和实时 acceptance 选择更接近 oracle 的 speculation budget。**

### 1.2 更强的论文版本

> **RISC-V/RVV 上的 verifier cost curve 不是后端黑箱常数，而是可由 microkernel 设计重塑的变量。VeriCurve-RV 将 `C_verify(T)` 从底层性能事实提升为 speculative decoding 的决策输入，并展示 verifier curve 与 speculation policy 的协同设计。**

---

## 2. 为什么不是已有工作

### 2.1 不是 shape-conditioned kernel selection

vLLM / Triton / cuBLASLt 这类系统已经会根据 problem shape 选择不同 kernel 或 tile 参数。这个方向不能作为创新点。

VeriCurve-RV 不做如下 claim：

```text
shape changed -> choose a different BLOCK_N/kernel
```

而是研究：

```text
verifier cost curve C_verify(T) changes -> optimal speculation budget changes
```

### 2.2 不是普通 adaptive speculation

TurboSpec / DISCO / Sequoia 等工作已经覆盖了很多“动态调 draft length / token tree / lookahead”的空间。

VeriCurve-RV 不把核心写成：

```text
observe goodput -> change draft length
```

而是写成：

```text
measure/model verifier curve -> combine with draft cost and acceptance -> choose draft budget
```

更进一步：

```text
microkernel design reshapes C_verify(T)
C_verify(T) reshapes speculation policy
```

### 2.3 不是纯 RVV kernel paper

如果只写：

```text
we implement a faster T=4 Q4/Q8 RVV verifier kernel
```

那就是 kernel paper，属于 TianchenRV/课题 2 范畴。

VeriCurve-RV 的 kernel 是使能器。论文真正要证明：

```text
microkernel curve changes inference-time speculation decisions
```

---

## 3. 最小系统要做什么

VeriCurve-RV 最小系统由四部分构成：

```text
1. Curve Profiler
   测 C_verify(T), C_draft(d), acceptance(d)

2. Curve Model
   解释和预测 C_verify(T) 的甜区/漂移

3. T-specialized Verifier Kernels
   最小实现 T=1/2/4/8 的 RVV low-bit verifier path

4. Curve-aware Speculation Controller
   在 llama.cpp speculative decoding 中选择 draft budget
```

系统不做 hot-path JIT，不做复杂 agent，不做每 token 搜索。推荐实现为：

```text
模型加载/首次运行/离线 profiling:
  生成或测量 C_verify(T)
  测量 C_draft(d)
  建 profile cache

推理运行时:
  每 8 或 16 个 token 更新 acceptance estimate
  查表选择 d ∈ {0,1,3,7,15}
  调用对应 verifier kernel
```

---

## 4. 文件结构

本设计拆成多个 Markdown 文件：

| 文件 | 内容 |
|---|---|
| `01_problem_and_positioning.md` | 问题定位、非目标、与现有工作的边界 |
| `02_core_concepts.md` | T、d、`C_verify(T)`、`C_draft(d)`、acceptance drift 等核心概念 |
| `03_system_architecture.md` | 系统架构、模块、数据流、接口 |
| `04_curve_model_and_controller.md` | 成本模型、controller 公式、运行时策略 |
| `05_kernel_design.md` | T-specialized RVV verifier kernels 的最小设计 |
| `06_experimental_plan.md` | 生死实验、RQ、baseline、metrics、ablation |
| `07_implementation_plan.md` | 工程路线、里程碑、风险和 fallback |
| `08_paper_outline.md` | 论文题目、abstract、贡献、章节结构、reviewer 质疑应答 |

---

## 5. 最小可发表版本

为了避免把第三课题做成一个过大的博士阶段工程，单篇论文建议收敛到：

```text
C1. RISC-V/RVV verifier curve characterization
C2. Lightweight curve model
C3. Minimal curve-shaping T-specialized verifier kernels
C4. Curve-aware speculation controller in llama.cpp
```

不要在单篇论文里强依赖：

- IntentIR 术语；
- TianchenRV 全自动生成；
- agent；
- 多框架通用 runtime；
- 大而全的 kernel marketplace。

博士大论文可以把三篇串起来；单篇论文要自包含。

---

## 6. 最重要的 Go / No-Go 实验

在正式写系统前，必须先做：

```text
1. 查当前 llama.cpp/RVV T=1/2/4/8 verifier path
2. 测 C_old(T)
3. 实现最小 T4 verifier kernel
4. 测 C_new(T)
5. 测 C_draft(d) 与 acceptance(d)
```

关键判断：

```text
如果 C_verify(T) 近线性，且 T-specialized kernel 压不下来：方向弱。

如果 C_verify(T) 单调次线性，但不同量化/硬件斜率漂移明显：方向可做，主论证用二维漂移。

如果常用 T∈{2,4,8} 内出现甜区/反弹：方向最强。
```

---

## 7. 术语表

| 术语 | 含义 |
|---|---|
| `T` | target verifier 一次处理的 token positions 数 |
| `d` | draft token 数，通常 `T=1+d` |
| `C_verify(T)` | target verifier 处理 T 个 token positions 的成本 |
| `C_draft(d)` | 生成 d 个 draft tokens 的成本 |
| `E_accept(d)` | 预计接受的 draft token 数 |
| verifier curve | `T -> C_verify(T)` 的曲线 |
| curve shaping | 通过 microkernel 设计改变 `C_verify(T)` 的形状 |
| acceptance drift | workload 变化导致 draft acceptance rate 变化 |
| curve-aware controller | 用 `C_verify(T)`, `C_draft(d)`, `E_accept(d)` 选择 draft budget 的控制器 |

