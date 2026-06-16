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

