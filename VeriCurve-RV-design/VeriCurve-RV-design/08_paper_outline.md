# 08. 论文大纲

## 1. 推荐标题

首选：

> **VeriCurve-RV: Co-designing Verifier Cost Curves and Speculation Policies for RISC-V LLM Inference**

备选：

> **Verifier-Cost-Curve-Aware Speculative Inference on RISC-V Vector Processors**

> **Beyond Fixed Speculation: Verifier Curve Modeling for Low-Bit LLM Inference on RISC-V**

---

## 2. Abstract 草稿

Speculative decoding accelerates autoregressive LLM inference by drafting multiple tokens and verifying them with the target model. Existing systems tune draft length or token-tree shape based on acceptance rate, goodput, or hardware-level throughput, but they usually treat target verification as a backend black box. This assumption is fragile on RISC-V Vector processors running low-bit LLM inference: the cost of verifying `T` token positions depends on the actual verifier microkernel, quantization layout, VLEN/LMUL choices, register pressure, and cache behavior.

We present **VeriCurve-RV**, a verifier-cost-curve-aware speculative inference system for llama.cpp on RISC-V. VeriCurve-RV characterizes the verifier cost curve `C_verify(T)` and draft cost `C_draft(d)`, builds a lightweight model explaining curve drift across quantization and RVV configurations, and introduces minimal T-specialized RVV verifier kernels to reshape the curve. At runtime, a lightweight controller selects the draft budget by minimizing expected cost per committed token using the measured verifier curve and recent acceptance estimates. Our evaluation shows that fixed draft lengths systematically mispredict under workload and deployment drift, while VeriCurve-RV approaches oracle decisions and avoids regressions under low-concurrency RISC-V inference.

---

## 3. 论文核心 claim

```text
C1. RISC-V/RVV low-bit verifier cost C_verify(T) is not a fixed backend constant.

C2. C_verify(T) varies with microkernel design, quantization, VLEN/LMUL, register pressure, cache/memory behavior.

C3. The optimal speculative draft length is a joint function of C_verify(T), C_draft(d), and acceptance drift.

C4. Fixed draft length is systematically suboptimal across workloads and deployments.

C5. A curve-aware controller can make better decisions with low overhead.
```

---

## 4. Contributions

### Contribution 1: Verifier curve characterization

首次系统测量 RISC-V/RVV low-bit LLM verifier 的：

```text
C_verify(T), T=1,2,4,8,16
C_draft(d), d=1,3,7,15
acceptance(d)
```

并展示跨：

```text
模型大小
量化格式
RVV 配置
workload
```

的漂移。

### Contribution 2: Lightweight verifier curve model

提出轻量模型解释：

```text
weight/dequant reuse
RVV accumulator/register pressure
cache/memory behavior
quantization block layout
```

如何决定 `C_verify(T)` 的甜区。

### Contribution 3: Minimal curve-shaping verifier kernels

实现最小 T-specialized RVV verifier kernels，用于证明：

```text
C_verify(T) can be reshaped by microkernel design.
```

### Contribution 4: Curve-aware speculation controller

在 llama.cpp 中实现：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

并用它动态选择 draft budget。

---

## 5. 章节结构

### Section 1: Introduction

重点故事线：

```text
Speculative decoding 的收益不只取决于 draft acceptance。
在 RISC-V/RVV low-bit inference 中，target verification 的物理成本曲线本身会漂移。
固定 draft length 在这种漂移下会误选。
```

避免说：

```text
我们发明 adaptive speculation。
我们第一个 kernel-centric scheduler。
我们第一个根据 shape 选 kernel。
```

### Section 2: Background and Motivation

内容：

```text
- speculative decoding 基本公式
- verifier T 的定义
- RISC-V/RVV low-bit inference 特点
- llama.cpp speculative decoding 和 RVV path
- 为什么 vLLM/Triton/cuBLASLt 的 shape-based dispatch 不是本文贡献
```

### Section 3: Verifier Curve Characterization

内容：

```text
- C_verify(T) 测量方法
- C_draft(d) 测量方法
- workload acceptance drift
- old llama.cpp/RVV path behavior
```

### Section 4: Curve Model and T-specialized Kernels

内容：

```text
- lightweight curve model
- T1/T2/T4/T8 kernel design
- curve shaping evidence
```

### Section 5: VeriCurve Controller

内容：

```text
- controller objective
- profile cache
- acceptance estimator
- runtime integration
- overhead control
```

### Section 6: Evaluation

研究问题：

```text
RQ1: What do RVV verifier curves look like?
RQ2: Can T-specialized kernels reshape curves?
RQ3: Does fixed draft length mispredict under drift?
RQ4: Does VeriCurve approach oracle?
RQ5: Where does speedup come from?
```

### Section 7: Discussion

内容：

```text
- limits
- applicability beyond RISC-V
- relation to TianchenRV
- when not to use speculation
```

### Section 8: Related Work

分组：

```text
- speculative decoding: Leviathan, Medusa, EAGLE, Sequoia, DISCO, TurboSpec
- LLM serving: vLLM, Sarathi, SGLang
- CPU/edge LLM inference: llama.cpp, tinyBLAS, KleidiAI
- RISC-V LLM inference
- kernel autotuning and dispatch: Triton, TVM, cuBLASLt
```

---

## 6. Reviewer 可能质疑与回答

### Q1: 这不就是 adaptive speculation 吗？

回答：

```text
不是。已有 adaptive speculation 主要调 draft policy，把 verifier 后端当成黑箱成本。VeriCurve-RV 研究 verifier cost curve 的来源、漂移和可重塑性，并把该曲线作为 draft policy 的输入。
```

### Q2: 这不就是写了一个更快的 RVV kernel 吗？

回答：

```text
不是。T-specialized kernel 是使能器。核心实验展示 new kernel only + fixed d 不等于 full system；curve-aware controller 在 mixed workload 下更接近 oracle。
```

### Q3: 这不就是 shape-based kernel selection 吗？

回答：

```text
不是。shape-based selection 是 shape 已经给定后选择 kernel。VeriCurve-RV 的决策变量是 draft budget，它决定 verifier shape T；该决策由 C_verify(T), C_draft(d), acceptance 共同决定。
```

### Q4: 如果 C(T) 单调次线性，controller 有什么用？

回答：

```text
单调次线性不代表固定 d 最优。不同部署的斜率不同，acceptance rate 随 workload 漂移，C_draft(d) 随 draft source 变化。VeriCurve-RV 面向的是二维漂移下的联合最优。
```

### Q5: 为什么只做 RISC-V？

回答：

```text
RISC-V/RVV 是最清晰的场景：low-bit verifier kernel 不成熟、低并发常见、draft cost 是 critical path、VLEN/LMUL/register pressure 强烈影响曲线。思想可推广，但本文做 RISC-V-first 深度系统。
```

### Q6: 为什么不用 TianchenRV 自动生成全部 kernel？

回答：

```text
本文保持自包含，用最小 RVV kernels 证明 curve shaping 和 controller 的系统价值。自动生成更多 curve-shaping kernels 是后续工作，也可接入 TianchenRV。
```

---

## 7. 必须避免的写法

避免：

```text
- kernel 是一等公民
- kernel-centered framework
- 我们让框架更容易插 kernel
- 我们第一个做 hardware-aware speculation
- 我们第一个根据 batch 选 kernel
- 我们做了一个 verifier plan metadata
```

建议写：

```text
- verifier cost curve is a decision input
- curve drift makes fixed speculation suboptimal
- RVV microkernel design reshapes the curve
- curve-aware controller adapts draft budget under acceptance and deployment drift
```

---

## 8. 最小投稿版本的贡献压缩

如果版面有限，只写：

```text
1. Measurement: C_verify(T), C_draft(d), acceptance drift on RVV
2. Minimal kernel: T4 verifier reshapes curve
3. Controller: curve-aware draft budget selection
4. Evaluation: mixed-workload fixed-d vs adaptive vs oracle
```

把成本模型写成轻量 explanation，不要展开成复杂预测系统。

