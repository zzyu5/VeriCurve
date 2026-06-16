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

