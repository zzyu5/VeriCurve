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

