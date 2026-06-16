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

