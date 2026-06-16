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

# 01. 问题定位与研究边界

## 1. 背景

第三课题的目标不是再做一个算子编译器，也不是再写一组 RVV kernel。前两个课题已经分别覆盖了：

```text
IntentIR:
  从优化 kernel 中恢复语义，并区分语义、正确性结构和 schedule hints。

TianchenRV:
  面向 RISC-V/RVV 生成、调优、部署 kernel。
```

第三课题要问的问题是：

> **当我们已经能生成或获得不同物理特性的 kernel 后，推理框架应该如何根据这些 kernel 的真实成本结构做上层 decoding 决策？**

最终选择的切口是 **speculative decoding 的 target verification 阶段**，因为它天然把 kernel 形状和推理策略连接起来：

```text
draft tokens 多 -> verifier 一次处理的 token positions T 增大
T 增大 -> verifier kernel 的成本 C_verify(T) 改变
C_verify(T) 改变 -> 最优 draft length 改变
```

这个链条形成了第三课题的核心。

---

## 2. 反复排除过的弱方向

### 2.1 “框架更容易插 kernel”不是贡献

这只是 engineering motivation，不是科研贡献。

问题：

```text
我们重构框架 -> kernel 更容易插入 -> 证明重构有价值
```

这是循环论证。

### 2.2 “根据 shape 选 kernel/block size”不是贡献

Triton、vLLM、cuBLASLt、TVM、TensorRT-LLM 都已经不同程度地做 shape-conditioned kernel selection。

所以不要写：

```text
不同请求 shape -> 选择不同 BLOCK_N/kernel
```

这不新。

### 2.3 “动态调 speculation length”不是贡献

TurboSpec、DISCO、Sequoia 等工作已经覆盖了 adaptive speculation / hardware-aware speculation 的大部分空间。

所以不要写：

```text
根据 goodput / acceptance rate 动态调 draft length
```

这也不新。

### 2.4 “写一个 multi-RHS RVV kernel”不是第三课题

如果核心贡献只是：

```text
T=4 verifier kernel 比原来快
```

那就是 kernel paper，属于 TianchenRV/课题 2。

第三课题必须证明：

```text
kernel 的成本曲线改变了上层 speculation 策略
```

---

## 3. 最终定位

最终定位是：

> **VeriCurve-RV：面向 RISC-V/RVV low-bit LLM inference 的 verifier cost curve characterization + modeling + curve-aware speculative decoding。**

更明确地说：

```text
不是：根据请求 shape 选 kernel。
而是：根据 verifier kernel 的 C_verify(T) 曲线选 draft budget。

不是：写一个更快 kernel。
而是：kernel 曲线如何成为推理框架决策输入。

不是：又一个 adaptive speculation。
而是：在 RISC-V/RVV 上，verifier curve 由 microkernel/量化/VLEN/LMUL/cache 共同决定，不能被当成 GPU-style 黑箱常数。
```

---

## 4. 为什么 RISC-V 是主战场

RISC-V/RVV 上这个问题更清楚，原因是：

1. low-bit LLM 推理 kernel 栈不如 GPU/cuBLAS/Triton 成熟；
2. edge / local / 单用户场景更常见，真实 request batching 不足；
3. draft model 在 CPU/RVV 上很可能是 critical-path cost，不能假设“很便宜”；
4. RVV 的 VLEN/LMUL/register pressure 会显著影响 multi-RHS verifier 的甜区；
5. llama.cpp 已有 speculative decoding / batch eval / quantized kernels，但现有参数多为用户静态配置，缺少 verifier-curve-aware decision。

这不是“GPU 已经做过，搬到 RISC-V”。RISC-V 上的 verifier curve 本身更需要被表征和设计。

---

## 5. 论文独立性

单篇论文建议不要强依赖 IntentIR 或 TianchenRV 的术语。可以在 introduction 或 discussion 中说：

```text
This direction complements prior kernel-lifting and RISC-V kernel-generation work.
```

但是系统本身要自包含：

```text
1. llama.cpp/RVV characterization
2. minimal T-specialized verifier kernels
3. curve-aware controller
4. end-to-end evaluation
```

博士大论文再把它和 IntentIR/TianchenRV 串起来。

---

## 6. 核心研究问题

```text
RQ0: 当前 llama.cpp/RVV 在 T=1/2/4/8 verifier 下到底走什么路径？
RQ1: RISC-V/RVV low-bit verifier 的 C_verify(T) 曲线长什么样？
RQ2: 这条曲线如何随 VLEN、LMUL、量化格式、模型大小、microkernel 设计变化？
RQ3: C_draft(d) 与 acceptance(d) 在 CPU/RVV 上如何影响最优 draft length？
RQ4: 固定 draft length 是否在跨 workload/hardware/quantization 漂移下系统性误选？
RQ5: Curve-aware controller 能否比 fixed speculation、goodput-only adaptive、new-kernel-only 更接近 oracle？
```

# 02. 核心概念

## 1. T：verifier token-width

`T` 是 VeriCurve-RV 的中心变量。

定义：

```text
T = target verifier 一次同时处理的 token positions 数量
```

不同情形：

```text
普通 decode:
  T = 1

speculate d 个 token:
  T = 1 + d

multi-user decode:
  T = 当前一起 decode 的真实请求数

prefill chunk:
  T = prompt chunk 中的 token 数
```

在本文中，重点是 speculative verification：

```text
T = 1 + draft length
```

---

## 2. T 不是 Triton BLOCK_N

需要严格区分：

```text
T / token-width:
  问题规模，表示本轮 verifier 要处理几个 token positions。

BLOCK_N / tile size:
  kernel 内部 schedule 参数，表示如何切分问题。
```

同一个 `T=4` 可以用不同 schedule 跑：

```text
schedule A: 4 次 T=1 vector dot
schedule B: 1 次 T=4 multi-RHS microkernel
schedule C: T=8 kernel + mask
```

VeriCurve-RV 关心的是：

```text
T 改变 -> verifier cost curve 改变 -> draft budget 决策改变
```

而不是简单地“请求 shape 改变 -> BLOCK_N 改变”。

---

## 3. C_verify(T)

定义：

```text
C_verify(T) = target model verifier 处理 T 个 token positions 的成本
```

可以按不同粒度测：

```text
microkernel-level:
  单个 q4/q8 matmul/verifier kernel 的 latency

layer-level:
  一个 transformer layer verification 的 latency

model-level:
  target model 完整 verification pass 的 latency
```

建议实验中都测，但 controller 的实现可以先用 model-level 或 layer-level aggregated curve。

---

## 4. C_draft(d)

定义：

```text
C_draft(d) = 生成 d 个 draft tokens 的成本
```

在 CPU/RVV 上，draft cost 不能忽略：

```text
ngram draft:
  不跑小模型，成本低，但 acceptance 依赖文本重复性。

small draft model:
  需要额外 forward，和 target 共享 CPU 核与内存带宽，可能很贵。

MTP/self-speculative:
  取决于 llama.cpp 支持和模型结构，成本/收益需要单独测。
```

VeriCurve-RV 不能只测 verifier cost，必须同时测 draft cost。

---

## 5. E_accept(d)

定义：

```text
E_accept(d) = 预计会被 target model 接受的 draft token 数
```

它随 workload 漂移：

```text
普通聊天:
  通常低或不稳定

代码补全/代码重构:
  ngram acceptance 可能较高

RAG 模板/结构化输出:
  重复格式多，acceptance 可能中高

reasoning 长输出:
  phase-dependent，可能漂移明显
```

这就是 controller 有价值的一个来源。

---

## 6. Controller 目标函数

最基本的 cost per committed token：

```text
J(d) = [ C_verify(1+d) + C_draft(d) ] / [ 1 + E_accept(d) ]
```

选择：

```text
d* = argmin_d J(d)
```

候选集合建议离散化：

```text
d ∈ {0, 1, 3, 7, 15}
T ∈ {1, 2, 4, 8, 16}
```

---

## 7. 为什么不是简单 decision flip

线性旧 kernel：

```text
C_verify(1+d) ≈ (1+d) C_verify(1)
```

因为：

```text
E_accept(d) ≤ d
C_draft(d) > 0
```

所以 speculation 基本不划算。这不是论文贡献，只是 sanity check。

真正的非平凡点是：

```text
1. C_verify(T) 在不同硬件/量化/microkernel 下曲线不同；
2. C_draft(d) 在不同 draft mechanism 下不同；
3. E_accept(d) 在不同 workload 下漂移；
4. 因此最优 d* 不是固定值。
```

---

## 8. Curve drift 的来源

### 8.1 Microkernel design

```text
T=1:
  single-RHS, low-latency, one accumulator group

T=4:
  multi-RHS, weight/dequant reuse, four accumulator groups

T=8:
  more reuse, but register pressure/caches may hurt
```

### 8.2 RVV 参数

```text
VLEN
SEW
LMUL
vector register budget
vsetvl strategy
accumulator layout
```

### 8.3 Quantization format

```text
Q4_0 / Q4_K_M / Q5 / Q8
scale layout
block size
unpack/dequant cost
```

### 8.4 Model size and cache

```text
layer weight size
L2/L3 capacity
memory bandwidth
cache miss rate
```

---

## 9. Curve shaping

VeriCurve-RV 的护城河不是“profile 一条曲线”，而是：

```text
microkernel design can reshape C_verify(T)
```

也就是说，同一个 verifier 语义，可以有不同曲线：

```text
curve A:
  T=1 best, T>1 weak

curve B:
  T=4 sweet spot

curve C:
  T=8 sweet spot but T=16 cliff
```

论文要证明：

```text
curve shape changes -> best d changes -> runtime policy should change
```

# 03. 系统架构

## 1. 总体架构

VeriCurve-RV 是一个在 llama.cpp/RVV 上实现的 curve-aware speculative inference 系统。系统由四层组成：

```text
┌──────────────────────────────────────────────────────────────┐
│ llama.cpp speculative decoding runtime                       │
│   - request loop                                              │
│   - ngram / draft model / MTP draft source                    │
│   - target model verifier                                     │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Curve-aware speculation controller                            │
│   input: C_verify(T), C_draft(d), acceptance estimate          │
│   output: draft length d, verifier variant T                   │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ Verifier curve layer                                          │
│   - profiler                                                  │
│   - curve cache                                               │
│   - lightweight cost model                                    │
│   - curve descriptors                                         │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ RVV low-bit verifier kernels                                  │
│   - existing llama.cpp RVV path                                │
│   - minimal T-specialized multi-RHS kernels                    │
│   - optional TianchenRV-generated variants                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. 核心数据流

### 2.1 离线/启动阶段

```text
1. Load model metadata:
   model size, quant format, layer shapes, thread config

2. Probe hardware:
   VLEN, extension support, core count, cache info if available

3. Benchmark verifier curves:
   C_verify(T) for T = 1,2,4,8,16

4. Benchmark draft cost:
   C_draft(d) for d = 1,3,7,15

5. Build curve cache:
   key = model + quant + backend + hardware + threads

6. Store profile:
   ~/.cache/vericurve-rv/<hash>.json
```

### 2.2 运行阶段

```text
1. Observe recent acceptance rate
2. Read C_verify(T) and C_draft(d)
3. Evaluate J(d)
4. Select d*
5. Draft d* tokens
6. Verify T=1+d* tokens with selected verifier path
7. Commit accepted prefix
8. Update acceptance statistics every N tokens
```

---

## 3. 主要模块

## 3.1 Curve Profiler

职责：

```text
- 测量 C_verify(T)
- 测量 C_draft(d)
- 记录 cache misses / RVV instruction count / memory bandwidth if available
- 输出 profile JSON
```

建议命令：

```bash
./llama-vericurve-profiler \
  -m model.gguf \
  --quant Q4_K_M \
  --threads 4 \
  --T-list 1,2,4,8,16 \
  --draft-list 1,3,7,15 \
  --output profile.json
```

Profile JSON 示例：

```json
{
  "model": "qwen2.5-3b-q4_k_m.gguf",
  "backend": "llama.cpp-rvv",
  "hardware": {
    "arch": "riscv64",
    "rvv": true,
    "vlen_bits": 128,
    "threads": 4
  },
  "verify_curve": {
    "T1": {"latency_ms": 100.0, "per_token_ms": 100.0},
    "T2": {"latency_ms": 135.0, "per_token_ms": 67.5},
    "T4": {"latency_ms": 190.0, "per_token_ms": 47.5},
    "T8": {"latency_ms": 360.0, "per_token_ms": 45.0},
    "T16": {"latency_ms": 900.0, "per_token_ms": 56.25}
  },
  "draft_curve": {
    "ngram": {
      "d1": {"latency_ms": 0.05},
      "d3": {"latency_ms": 0.10},
      "d7": {"latency_ms": 0.20}
    },
    "draft_model": {
      "d1": {"latency_ms": 10.0},
      "d3": {"latency_ms": 25.0},
      "d7": {"latency_ms": 60.0}
    }
  }
}
```

---

## 3.2 Curve Cache

Profile key：

```text
hash(
  model_arch,
  model_size,
  quant_format,
  backend_commit,
  hardware_id,
  vlen,
  threads,
  verifier_kernel_set
)
```

作用：

```text
- 避免每次启动都重新 profile
- 允许跨运行复用
- 支持 fallback：profile 不存在时使用 conservative default
```

---

## 3.3 Cost Model

输入：

```text
C_verify(T)
C_draft(d)
acceptance estimate
```

输出：

```text
estimated cost per committed token
```

基本公式：

```text
J(d) = [ C_verify(1+d) + C_draft(d) ] / [ 1 + E_accept(d) ]
```

扩展项：

```text
J(d) = [ C_verify(1+d) + C_draft(d) + C_overhead(d) + penalty(d) ]
       / [ 1 + E_accept(d) ]
```

其中：

```text
C_overhead(d): sampler / batch preparation / rollback/commit overhead
penalty(d): latency/SLO penalty, excessive memory penalty
```

---

## 3.4 Acceptance Estimator

实现建议：

```text
EWMA acceptance:
  acc_rate <- alpha * current_accept + (1-alpha) * acc_rate

Per-workload bucket:
  chat / code / structured / unknown

Per-draft-source bucket:
  ngram / draft_model / MTP
```

最小实现：

```c
struct vc_accept_stats {
    float ewma_accept_per_draft;
    float ewma_full_accept_rate;
    int   window_tokens;
};
```

---

## 3.5 Curve-aware Controller

最小逻辑：

```pseudo
candidate_d = [0, 1, 3, 7, 15]
best = 0
best_score = C_verify(1)

for d in candidate_d:
    T = 1 + d
    if not curve.supports(T):
        continue
    C_v = C_verify(T)
    C_d = C_draft(d)
    E_a = estimate_accept(d)
    score = (C_v + C_d) / (1 + E_a)
    if score < best_score * safety_margin:
        best = d
        best_score = score

return best
```

Safety margin：

```text
避免预测噪声导致频繁切换。
例如只有 predicted improvement > 5% 才切换。
```

Update frequency：

```text
每 8 或 16 个 generated tokens 更新一次；
中间保持 d 不变。
```

---

## 3.6 Verifier Kernel Dispatch

控制器输出：

```text
draft length d
T = 1 + d
```

runtime 调用：

```text
if T == 1:
  verify_T1(...)
elif T <= 2:
  verify_T2(...)
elif T <= 4:
  verify_T4(..., mask=T)
elif T <= 8:
  verify_T8(..., mask=T)
else:
  fallback_generic_verify(...)
```

注意：

```text
T-specific kernel 是可选增强；
系统也可以先用现有 llama.cpp kernel profile 做 controller。
```

但是论文最好包含最小 T-specialized kernel，用来证明 `C_verify(T)` 可以被 microkernel 设计重塑。

---

## 4. 与 llama.cpp 的集成点

### 4.1 Speculative decoding entry

改动点：

```text
原来：用户通过 --spec-draft-n-max 等静态参数指定 draft length。
现在：VeriCurve controller 根据 profile 选择 draft length。
```

保留用户参数作为上限：

```text
--vc-max-draft 15
--vc-candidates 0,1,3,7,15
--vc-update-interval 16
```

### 4.2 Draft source

支持：

```text
ngram draft:
  最优先，CPU/RVV 上成本低。

small draft model:
  作为可选，需要实测 C_draft(d)。

MTP/self-speculative:
  如果 llama.cpp 当前支持，则作为第三类 draft source。
```

### 4.3 Target verifier

最小实现：

```text
只改 verification batch size 的选择；
优先复用 llama.cpp 现有 target eval。
```

增强实现：

```text
接入 T-specialized RVV low-bit verifier kernel。
```

---

## 5. 运行模式

### 5.1 Profile-only mode

```bash
./llama-cli -m model.gguf --vericurve-profile-only
```

用途：生成曲线数据和论文图表。

### 5.2 Static curve-aware mode

```bash
./llama-cli -m model.gguf --vericurve --vc-static
```

启动时选择一个全局最佳 `d`，运行中不更新。

### 5.3 Adaptive curve-aware mode

```bash
./llama-cli -m model.gguf --vericurve --vc-adaptive
```

运行时根据 acceptance drift 更新 `d`。

### 5.4 Oracle mode

```bash
./llama-cli -m model.gguf --vericurve-oracle
```

离线穷举不同 `d`，用于评测上界。

---

## 6. 热路径开销控制

VeriCurve-RV 不允许在热路径上引入复杂开销。

设计原则：

```text
- 不在 token hot path 中 profile
- 不在 hot path JIT
- 不每 token 穷举 benchmark
- 不用 LLM agent 做 runtime decision
- 只做查表 + 简单公式
```

复杂度：

```text
O(number_of_candidate_d)
通常候选只有 5 个：0,1,3,7,15
```

预计控制器开销：微秒级。目标 verifier 一次 pass 通常是毫秒级到百毫秒级。

---

## 7. Fallback 设计

如果 profile 缺失：

```text
use conservative d=0 or user-specified fixed speculation
```

如果 predicted speedup 小于阈值：

```text
turn off speculation
```

如果 acceptance 低：

```text
reduce d or turn off speculation
```

如果 kernel 不支持目标 T：

```text
use nearest supported T with mask or fallback generic path
```

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

# 05. T-specialized RVV Verifier Kernels 设计

## 1. 目标

T-specialized kernel 不是论文唯一贡献，而是 VeriCurve-RV 的使能器。它的任务是：

> **创造或重塑 `C_verify(T)` 曲线，使 verifier cost curve 不再是旧后端给定的黑箱。**

最小版本只需要覆盖一个清晰路径，例如：

```text
Q4_0 × Q8_0 verifier_T1/T2/T4/T8
```

或者当前 TianchenRV/llama.cpp 最容易接上的 Q4_K_M/Q8 path。

---

## 2. 为什么需要 T-specialized kernel

如果旧路径是：

```text
for t in T tokens:
    run single-RHS vec_dot
```

那么：

```text
C_verify(T) ≈ T × C_verify(1)
```

speculation 基本不划算。

T-specialized multi-RHS kernel 改成：

```text
load/decode weight block once
apply it to multiple RHS activation vectors
accumulate multiple outputs
```

目标：

```text
C_verify(4) << 4 × C_verify(1)
```

---

## 3. Kernel 语义

对每个 linear/verifier 子问题：

```text
Y[T, O] = X[T, K] × W[K, O]
```

低比特 weight-only quantization 下：

```text
W: quantized blocks, e.g. Q4_0 / Q4_K_M / Q5 / Q8
X: activation, e.g. fp16/q8/f32 depending llama.cpp path
Y: float accumulation / output dtype
```

---

## 4. Variant 设计

### 4.1 T1 kernel

```text
目标：single-token decode latency 最低
特点：
  - one RHS
  - one accumulator group
  - low register pressure
  - optimized for T=1
```

### 4.2 T2 kernel

```text
目标：低风险 multi-RHS 复用
特点：
  - two RHS
  - two accumulator groups
  - moderate weight/dequant reuse
  - register pressure still safe
```

### 4.3 T4 kernel

```text
目标：speculative verification 常用甜点
特点：
  - four RHS
  - weight block load/decode once
  - four accumulator groups
  - LMUL/unroll/reduction strategy must be retuned
```

### 4.4 T8 kernel

```text
目标：高 acceptance workload / code / structured output
特点：
  - eight RHS
  - strongest weight reuse potential
  - high register pressure
  - may hit spill/cache cliff
```

---

## 5. RVV-specific design variables

需要在实验里探索：

```text
SEW
LMUL
VL strategy
vsetvl placement
unroll factor
number of RHS accumulators
accumulator layout
reduction timing
weight unpack/dequant placement
activation layout
prefetch distance
thread partition
```

---

## 6. 关键 dataflow

### 6.1 不好的 T=4 实现

```pseudo
for rhs in 0..3:
    for block in K_blocks:
        load weight block
        decode weight block
        load activation[rhs]
        dot
```

这等价于 4 次 T1。

### 6.2 目标 T=4 实现

```pseudo
for block in K_blocks:
    w = load_quant_weight_block()
    w_decoded = decode_once(w)

    x0 = load_activation(rhs=0, block)
    x1 = load_activation(rhs=1, block)
    x2 = load_activation(rhs=2, block)
    x3 = load_activation(rhs=3, block)

    acc0 += dot(w_decoded, x0)
    acc1 += dot(w_decoded, x1)
    acc2 += dot(w_decoded, x2)
    acc3 += dot(w_decoded, x3)

reduce/store acc0..acc3
```

目标收益：

```text
- weight load/decode amortization
- scale/dequant amortization
- better arithmetic intensity
```

风险：

```text
- register pressure
- LMUL too large -> fewer effective vector register groups
- spill
- activation stride/cache issues
```

---

## 7. Kernel API 设计

建议不要一开始改完整 ggml ABI。先做 microbenchmark API：

```c
void rvv_q4q8_verify_T4(
    const void * weight_blocks,
    const void * activation_TK,
    float * output_TO,
    int K,
    int O,
    int T,
    int stride_x,
    int stride_y
);
```

然后再接入 llama.cpp 的 target verification path。

T-specific wrapper：

```c
rvv_q4q8_verify_T1(...)
rvv_q4q8_verify_T2(...)
rvv_q4q8_verify_T4(...)
rvv_q4q8_verify_T8(...)
```

对于 T 不等于支持值：

```text
T=3 -> T4 with mask 或 T2+T1
T=5 -> T8 with mask 或 T4+T1
```

---

## 8. 与 TianchenRV 的关系

单篇论文建议不要强依赖 TianchenRV。但在系统路线中，TianchenRV 可以作为 variant generator：

```text
input: low-bit verifier op + target RVV capability + T bucket
output: T-specialized RVV kernel variant
```

TianchenRV 可探索：

```text
T bucket as tuning key:
  T=1,2,4,8

Gearbox choices:
  LMUL, unroll, accumulator layout, reduction timing
```

论文写法建议：

```text
The prototype uses minimal hand-written/TianchenRV-assisted RVV kernels.
Automated generation of a broader kernel family is future work.
```

这样论文自包含，也不绑定未发表的第二课题。

---

## 9. 需要证明的 kernel 事实

必须展示：

```text
1. T-specific kernels emitted body/dataflow 真的不同
2. T4/T8 不是简单重复 T1
3. C_verify(T) 曲线确实被 kernel design 改变
4. 收益来自 weight/dequant reuse 和 RVV dataflow，而不是少量 dispatch overhead
```

建议指标：

```text
latency
per-token latency
RVV instruction count
memory bandwidth
cache miss rate
load/decode count if instrumentable
register spill indicator if available
```

---

## 10. 最小成功标准

```text
T4 kernel:
  C_new(4) / C_new(1) <= 2.5  初步可用
  <= 2.0  很好
  <= 1.7  非常强

T8 kernel:
  如果 <= 3.5，说明高 draft 有潜力
  如果反弹明显，也支持 controller 需要判断甜区
```

如果 T4 都压不下来，这条线需要暂停。

# 06. 实验计划

## 1. 实验总目标

证明 VeriCurve-RV 不是简单的 kernel optimization，也不是普通 adaptive speculation，而是：

> **verifier cost curve `C_verify(T)` 的形状和漂移会导致固定 draft length 系统性误选；curve-aware controller 能利用 RISC-V/RVV low-bit verifier 的实际成本结构，做出更接近 oracle 的 speculation 决策。**

---

## 2. 生死实验

### Experiment 0: 当前 llama.cpp/RVV path 分析

目标：确认当前 T>1 verifier 是 multi-RHS 还是多次 vec_dot。

方法：

```text
- 读 llama.cpp/ggml low-bit mul_mat 路径
- 插桩统计 T=1/2/4/8 时调用了哪些 kernel
- perf 记录函数调用和热点
- 比较 T=4 是否大约等于 4 次 T=1
```

输出：

```text
current_path.md
call_trace_T1.txt
call_trace_T4.txt
C_old_T.csv
```

判断：

```text
如果 T>1 已经有强 multi-RHS path：kernel 使能贡献变小。
如果 T>1 退化为多次 vec_dot：gap 明确。
```

---

### Experiment 1: C_old(T) 曲线

配置：

```text
T = 1,2,4,8,16
quant = Q4_0, Q4_K_M, Q8
model = 1B, 3B, 7B if possible
threads = 1, 4, maybe 8
```

指标：

```text
latency per verification pass
per-position latency
cache miss rate
memory bandwidth
RVV instruction count
```

输出：

```text
C_old_verify.csv
C_old_figures/
```

关键图：

```text
C(T)/C(1)
C(T)/T
cache miss vs T
```

---

### Experiment 2: Minimal T4/T8 kernel

目标：证明 `C_verify(T)` 可被 microkernel design 重塑。

先做：

```text
Q4_0 × Q8_0 verify_T4
```

再做：

```text
verify_T2
verify_T8
```

比较：

```text
old generic path
new T-specialized path
```

输出：

```text
C_new_verify.csv
old_vs_new_curve.png
```

判断：

```text
如果 C_new(4) 仍接近 4C_new(1): 方向弱。
如果 C_new(4) <= 2C_new(1): 方向强。
```

---

### Experiment 3: C_draft(d) 与 acceptance

Draft source：

```text
ngram
small draft model if feasible
MTP/self-speculative if available
```

Workload：

```text
chat
code completion / code refactor
RAG template
structured JSON/tool output
reasoning output
mixed workload
```

测：

```text
C_draft(d), d=1,3,7,15
actual accepted tokens
acceptance per draft token
full accept probability
```

输出：

```text
C_draft.csv
acceptance.csv
```

---

## 3. 主要 Research Questions

### RQ1: RISC-V/RVV verifier curve 是否有可利用结构？

问题：

```text
C_verify(T) 是否次线性？
是否存在甜区？
甜区是否随量化、模型、线程、硬件变化？
```

图：

```text
C_verify(T)/C_verify(1)
C_verify(T)/T
```

结论模板：

```text
We find that the verifier curve is not a fixed black box; it shifts across quantization and RVV configuration.
```

---

### RQ2: T-specialized microkernel 是否能重塑曲线？

对比：

```text
old llama.cpp/RVV path
new T-specialized verifier kernels
```

关注：

```text
T=2/4/8 的 curve slope 是否改变
是否出现新的 sweet spot
是否出现 register/cache cliff
```

---

### RQ3: fixed draft length 是否系统性误选？

Baseline：

```text
fixed d=1
fixed d=3
fixed d=7
offline-best fixed d per workload
offline-best fixed d over mixed workload
```

重点：

```text
在 mixed workload 中，单一 fixed d 是否明显偏离 oracle？
```

---

### RQ4: Curve-aware controller 是否接近 oracle？

对比：

```text
no speculation
llama.cpp default fixed speculation
fixed d
best-fixed-over-mixed
goodput-only adaptive
VeriCurve-RV
oracle
```

指标：

```text
tokens/s
ms/token
speedup vs no speculation
regression rate
oracle gap
controller overhead
```

---

### RQ5: 收益来自哪里？

Ablation：

```text
A0: old kernel + fixed d
A1: old kernel + curve-aware controller
A2: new T-specialized kernel + fixed d
A3: new T-specialized kernel + goodput-only adaptive
A4: new T-specialized kernel + VeriCurve controller
A5: oracle
```

理想结论：

```text
A2 shows kernel enables better C(T), but fixed d is unstable.
A4 improves robustness under acceptance drift and approaches oracle.
```

---

## 4. Baselines

### 4.1 System baselines

```text
B0: llama.cpp no speculation
B1: llama.cpp fixed speculation, user-selected d
B2: llama.cpp default speculation settings
B3: goodput-only adaptive controller
B4: new kernels only + fixed d
B5: VeriCurve-RV
B6: oracle d per segment
```

### 4.2 Kernel baselines

```text
K0: scalar / non-RVV if available
K1: existing llama.cpp RVV path
K2: existing tinyBLAS/llamafile path if enabled
K3: T-specialized RVV T1/T2/T4/T8
```

### 4.3 Controller baselines

```text
C0: always d=0
C1: fixed d=1
C2: fixed d=3
C3: fixed d=7
C4: offline-best fixed d per workload
C5: offline-best fixed d over mixed workload
C6: EWMA goodput adaptive
C7: VeriCurve
C8: oracle
```

---

## 5. Workloads

建议数据集/任务类型：

```text
1. Chat
   low/unstable acceptance

2. Code completion / refactoring
   high ngram acceptance potential

3. RAG template QA
   repeated context and format

4. Structured JSON/tool output
   repetitive format, medium/high acceptance

5. Reasoning long outputs
   acceptance drift across phases

6. Mixed workload
   sequence of above workloads to force drift
```

---

## 6. Metrics

### Performance

```text
tokens/s
ms/token
TTFT if relevant
verification latency
end-to-end generation latency
speedup vs no speculation
speedup vs fixed d
oracle gap
```

### Curve metrics

```text
C_verify(T)
C_verify(T)/C_verify(1)
C_verify(T)/T
C_draft(d)
E_accept(d)
J(d)
```

### Hardware counters

```text
L1/L2/L3 miss if available
memory bandwidth
RVV instruction count
cycles
instructions
branch/cache statistics
```

### Robustness

```text
regression rate vs no speculation
wrong-choice rate vs oracle
controller switch frequency
controller overhead
```

---

## 7. 必须出现的图表

```text
Figure 1: System overview
Figure 2: C_verify(T) curves old vs new kernels
Figure 3: C_verify(T)/T per quant/hardware
Figure 4: C_draft(d) and acceptance(d) per workload
Figure 5: Optimal d heatmap over acceptance and C(T) curve
Figure 6: Fixed d vs VeriCurve vs oracle under mixed workload
Figure 7: Ablation new kernel only vs controller only vs full
Figure 8: Hardware counter explanation of curve shape
```

---

## 8. 成功标准

最低成功：

```text
- 当前 RVV path T>1 不理想，C_old(4) 接近线性；
- T-specialized kernel 能明显改变 C_verify(T)；
- Curve-aware controller 在 mixed workload 赢 best-fixed-over-mixed。
```

强成功：

```text
- T=4 或 T=8 存在清晰甜区；
- 甜区随量化/硬件漂移；
- controller 接近 oracle，且避免 fixed speculation regression。
```

失败条件：

```text
- C_verify(T) 全部近线性，T-specialized kernel 压不下来；
- C_draft(d) 太高导致所有 speculation 都不划算；
- fixed best d 在所有 workload 上都接近 oracle；
- controller overhead 或 misprediction 导致 regression。
```

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

