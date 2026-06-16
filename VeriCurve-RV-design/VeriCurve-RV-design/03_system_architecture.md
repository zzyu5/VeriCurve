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

