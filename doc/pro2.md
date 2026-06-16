你现在应该让 agent 做的不是“继续优化这个 direct T4”，而是**重新开一个 Go/No-Go 树**。当前实验已经给出一个很清楚的负结果：

```text
current llama.cpp/RVV Q4_0 × Q8_0 path:
  T=1/2/4/8/16 almost perfectly linear

minimal direct R1T4:
  correctness OK
  performance worse than 4 × T1

结论：
  token-width 可见本身不够；
  R=1,T=4 direct vecdot 路线 No-Go。
```

所以我建议接下来分成两个层面推进：

1. **思路层面重新分叉**：现在到底保留 VeriCurve-RV，还是转向 Schedule-at-Inference-Time / Cache-aware / pure characterization？
2. **实验层面让 agent 做一组明确任务**：每条分叉都有 Go/No-Go 门槛，做完之后给你一个新的实验结论，而不是继续凭感觉讨论。

---

# 一、思路上怎么改

## 1. 主线暂时保留：VeriCurve-RV，但核心从 “T-visible” 改成 “curve-shaping”

当前负结果说明：

```text
T visible != curve shaping
```

你不能再说：

> 让 token-width 进入 kernel 就能摊薄 verifier cost。

现在应该改成：

> **VeriCurve-RV 研究的是：RISC-V/RVV low-bit verifier 的 `C_verify(T)` 曲线能不能被 microkernel layout / R×T blocking / packing 重新塑形；只有当曲线被塑形之后，curve-aware speculation controller 才有意义。**

也就是说，主线不是 controller，主线是：

```text
current path: repeated T1, C(T) linear
failed path: R1T4 direct, slower
next question: is there a materially different RTile × TTile / repacked microkernel that can bend C(T)?
```

如果能把 T=4 从接近 `4×T1` 压到 `2~3×T1`，VeriCurve-RV 继续；如果压不下来，VeriCurve-RV 作为系统论文就应该停。

---

## 2. 不要把 “kernel profile-driven scheduler” 当主创新

Claude 文档里最后那个 “kernel-centric scheduler” 直觉对，但仍然太泛。你们已经证明 FrontierFill 原样会被 TurboSpec / Sequoia / DISCO 一类工作威胁；文档里也明确说 FrontierFill 作为独立创新不够新，需要通过 RISC-V 平台特征重新定位。

所以不要让 agent 现在写：

```text
kernel-centric scheduler
profile-driven scheduler
adaptive speculation controller
```

这些都必须等 **C_new(T)** 出来之后再说。现在没有可用的新 verifier curve，scheduler 没有物理基础。

---

## 3. Schedule-at-Inference-Time 可以作为第二分支，但不能马上变主线

这个方向是：

> 同一个 kernel 有多个 schedule variants，运行时根据 batch / token-width 选择 variant。

它和 IntentIR 的博士叙事很顺，因为 IntentIR 明确把 Layer A/B 和 Layer C 分开：Layer C 记录 tile size、thread count、vector width、pipeline depth 等非绑定 schedule hints，改变 Layer C 会影响性能但不改变语义。 IntentIR 也已经证明后端可以 retune source schedule，在 RVV 上比 freeze-tiling 更好，并达到 4.48× single-thread、3.00× 16-thread geomean speedup。

但作为第三课题单篇论文，它有两个风险：

```text
1. 太依赖 IntentIR/TianchenRV，单篇独立性弱；
2. “不同 shape 选不同 variant”本身很普通，必须证明 variant crossover。
```

所以它只能作为一个**并行 Go/No-Go 分支**：

```text
如果不同 schedule variant 在不同 T/B 下有交叉：
  可以考虑 Schedule-at-Inference-Time

如果一个 dominant variant 全部最好：
  这个方向 No-Go
```

Claude 文档里也把这个方向的关键实验写得很清楚：测 `T(kernel, variant, batch_size)` 矩阵；如果不同 variant 在不同 B 下确实交叉，则方向成立；如果存在一个 dominant variant，动态切换没意义。

---

## 4. Cache-aware 可以作为 fallback characterization，不应做主线

Cache-aware speculation 是可能的 fallback，但不是现在的主线。原因是你已经测到 current Q4_0 path 的 `C_old(T)` 几乎完美线性，这说明在当前配置下自然 batch 没有产生明显 cache / weight reuse 摊薄。

但 cache-aware 仍可作为 fallback：

```text
如果不同模型大小 / 量化 / working set 下出现 cache cliff，
可以做 RISC-V verifier curve characterization paper。

如果所有低比特路径都接近线性，
说明 RISC-V/llama.cpp 当前 batch amortization 很弱，
这本身也是一个有价值的负结果，但不够做强系统论文。
```

Claude 文档里 cache-aware 方向的核心是：CPU/RISC-V 有 cache hierarchy，T(B) 曲线可能受 weight 是否留在 cache 影响，而 GPU speculative decoding 的分析常把 verify cost 当黑箱或 flat-memory roofline。 这个观点可以保留，但必须由 perf / cache miss / synthetic working-set 实验证明。

---

# 二、给 agent 的具体任务树

下面这段可以直接丢给 agent。建议新开一个 Trellis 总任务：

```text
.trellis/tasks/06-17-post-direct-t4-go-nogo/
```

任务名：

```text
post-direct-t4-go-nogo
```

任务目标：

```text
After direct R1T4 failed, determine whether VeriCurve-RV should continue via
(1) layout/RTile×TTile curve-shaping kernels,
(2) schedule-variant runtime selection,
(3) cache-aware characterization,
or be stopped.
```

---

# Part A：主线 Go/No-Go —— curve-shaping microkernel 是否还活着

## Task A0：写清楚继承结论

让 agent 在 `prd.md` 开头写：

```text
Previous evidence:
  current llama.cpp/RVV Q4_0 × Q8_0 path:
    trace path = ggml_vec_dot_q4_0_q8_0, nrc=1
    C_old(T) almost perfectly linear
  minimal direct R1T4:
    correctness OK
    new_t4 = 1.695 × old_t4
    new_t4 = 6.770 × old_t1

Interpretation:
  T visibility alone is insufficient.
  Direct R=1,T=4 vecdot is No-Go.
  Any next kernel must be materially different:
    row-blocking, token-blocking, RHS packing, weight repacking,
    or reuse of existing repack/GEMM machinery.
```

产物：

```text
research/inherited_conclusion.md
```

---

## Task A1：审计现有 repack / llamafile / tinyBLAS / 16x1 路径

目的：不要先写新 kernel，先确认 llama.cpp 里已经有的 repack/GEMM machinery 为什么没帮上忙。

让 agent 查：

```text
ggml/src/ggml-cpu/repack.cpp
ggml/src/ggml-cpu/arch/riscv/*
ggml/src/ggml-cpu/llamafile/*
ggml_compute_forward_mul_mat path
```

重点查这些问题：

```text
1. q4_0_16x1_q8_0 / q4_K_16x1_q8_K / q8_0_16x1_q8_0 是否存在？
2. 它们是否真的支持 RVV？
3. guard 条件是什么？
   - __riscv_zvfh
   - VLEN=256
   - shape alignment
   - quant type
   - tensor layout
   - compile flags
4. 当前硬件是否满足这些条件？
5. T=4 prompt / microbench 有没有进入这些 path？
6. 如果没进入，是因为 build flag、shape、layout、quant、还是 code path 本身不支持？
```

最好加一个轻量 trace：

```text
GGML_VERICURVE_REPACK_TRACE=1
```

只打印/记录计数，不要每次循环打印：

```text
path_name
call_count
quant_type
nr/nc/nrc/bs
shape
guard_result
reason_not_selected
```

产物：

```text
research/repack_path_audit.md
results/repack_path_conditions.csv
patches/repack_trace.patch
```

### A1 Go/No-Go

```text
GO-existing-repack:
  existing repack/GEMM path exists but is not selected due to guard/config/shape,
  and it can be safely forced in microbenchmark.

GO-custom-RT-kernel:
  existing repack path unavailable or irrelevant for current Q4_0 × Q8_0 RVV.

NO-GO-repack-branch:
  existing repack path already selected and still near-linear.
```

---

## Task A2：建立 R×T microkernel benchmark matrix

目的：验证真正的 low-bit micro-GEMM 是否能 reshape curve。

这次不要再只测：

```text
R=1,T=4
```

而是测矩阵：

```text
Rtile ∈ {1,2,4,8}
Ttile ∈ {1,2,4,8}
```

其中：

```text
R = output rows / weight rows
T = token positions / RHS columns
```

至少实现/测这些 case：

```text
R1T1: current vecdot baseline
R1T4: previous failed direct T4, kept as reference
R2T2
R2T4
R4T1
R4T2
R4T4
```

如果 R4 太复杂，先做：

```text
R2T2 and R2T4
```

核心假设：

```text
old path:
  one row × one token repeated

failed path:
  one row × four tokens

possible useful path:
  multiple rows × multiple tokens
```

因为 R 维可以带来 activation reuse，T 维可以带来 weight/dequant reuse；只做 T 不做 R，可能解释了上次失败。

产物：

```text
scripts/bench_rtile_ttile_kernel.cpp
research/rtile_ttile_design.md
results/rtile_ttile_matrix.csv
patches/rtile_ttile_harness.patch
```

---

## Task A3：layout ablation：RHS packing、weight row packing、both

让 agent 不要只写函数循环，而要明确做 layout ablation。

### Layout 0：no packing

```text
independent row pointers
independent RHS pointers
```

这是 baseline，很可能慢。

### Layout 1：packed RHS

把多个 token 的 Q8 RHS 按 block 交错：

```text
for each qblock k:
  y0[k], y1[k], y2[k], y3[k]
```

测 packing cost：

```text
C_pack_rhs(T)
C_kernel_packed_rhs(T)
C_total = C_pack_rhs + C_kernel
```

### Layout 2：row-blocked weights

把多个 Q4 rows 按 block 交错：

```text
for each qblock k:
  Wrow0[k], Wrow1[k], Wrow2[k], Wrow3[k]
```

测：

```text
C_pack_weight_once
C_kernel_rowblocked
```

注意 weight pack 可以 load-time amortize，RHS pack 通常每 step 都要算，所以必须分开计。

### Layout 3：packed RHS + row-blocked weights

这是最接近真正 micro-GEMM 的版本。

产物：

```text
research/layout_ablation.md
results/layout_ablation.csv
patches/layout_pack_harness.patch
```

---

## Task A4：必须用 best-T1 做判据

这点很重要。不要只比较：

```text
candidate_T4 vs old_T4
```

因为如果新 layout / row-blocked kernel 也把 T1 做快了，speculation 是否有价值要看：

```text
candidate_T4 / best_T1
```

报告格式必须包含：

```text
C_old_T1
C_old_T4
C_best_T1
C_candidate_T4_no_pack
C_candidate_T4_with_pack
C_candidate_T4_total
speedup_vs_old_T4 = C_old_T4 / C_candidate_T4_total
curve_ratio = C_candidate_T4_total / C_best_T1
correctness_max_abs
correctness_max_rel
```

产物：

```text
research/curve_shaping_go_nogo.md
results/curve_shaping_summary.csv
```

### A4 Go/No-Go

```text
STRONG GO:
  C_candidate_T4_total / C_best_T1 <= 2.5
  and C_candidate_T4_total <= 0.65 × C_old_T4
  and correctness passes

GO:
  C_candidate_T4_total / C_best_T1 <= 3.0
  and C_candidate_T4_total <= 0.75 × C_old_T4
  and correctness passes

CONDITIONAL:
  C_candidate_T4_total / C_best_T1 <= 3.4
  or C_candidate_T4_total <= 0.85 × C_old_T4
  and correctness passes
  => allow exactly one more optimization pass

NO-GO:
  C_candidate_T4_total / C_best_T1 > 3.4
  and C_candidate_T4_total > 0.85 × C_old_T4
```

如果 A4 是 NO-GO，就不要做 controller，也不要测 C_draft，VeriCurve system track 暂停。

---

# Part B：第二分支 Go/No-Go —— schedule variant 是否有交叉

这个分支用于判断是否转向：

```text
Schedule-at-Inference-Time / Runtime Schedule Polymorphism
```

这个方向和 IntentIR 的三层设计契合，因为 IntentIR 的 Layer C 本来就是非绑定 schedule hint，后端可以 retune；论文中也已有 host-side dispatch selecting among pre-tuned tile variants 的事实。 但它必须靠数据证明，不然就是普通 autotuning。

## Task B1：构造 schedule variants

不需要完整 TianchenRV。可以先在 harness 里用 macro / flags 构造 variants：

```text
V0: current old vecdot
V1: LMUL small / low register pressure
V2: LMUL large / wider throughput
V3: deferred-wide reduction style
V4: row-blocked
V5: token-blocked
V6: row+token blocked
```

每个 variant 都要记录：

```text
variant_id
LMUL
SEW
unroll
Rtile
Ttile
layout
reduction_strategy
```

产物：

```text
research/variant_space.md
results/variant_manifest.csv
```

---

## Task B2：测 T(variant, B) 矩阵

测：

```text
B/T ∈ {1,2,4,8,16}
variant ∈ V0..Vn
quant = Q4_0 × Q8_0 first
threads = 1
```

输出：

```text
latency_ms
ratio_to_old_T1
winner_variant
runner_up
margin
```

产物：

```text
results/variant_by_T_matrix.csv
research/variant_crossover_analysis.md
```

### B2 Go/No-Go

```text
GO-runtime-variant:
  at least two variants are best for different T values,
  and winner margin >= 7% in at least two T buckets,
  and best-dynamic over mixed T distribution beats best-static by >= 8%.

CONDITIONAL:
  crossover exists but margin < 7%,
  or best-dynamic beats best-static by 3%~8%.

NO-GO:
  one dominant variant is within 3% of best for all T,
  or dynamic selection beats best-static by < 3%.
```

如果 B2 GO，可以考虑一个单独方向：

> Batch-Conditioned Schedule Selection for RISC-V LLM Kernels

如果 B2 NO-GO，不要再讨论 runtime schedule polymorphism。

---

# Part C：第三分支 Go/No-Go —— cache-aware characterization 是否可独立成文

这个分支是 fallback，不要求新 kernel 成功。

## Task C1：跨模型 / 量化测 C_old(T)

测：

```text
model_size ∈ {small synthetic, 1B, 3B, 7B if available}
quant ∈ {Q4_0, Q4_K_M, Q5, Q8}
T ∈ {1,2,4,8,16}
threads ∈ {1, maybe 4}
```

报告：

```text
C_old(T)
C_old(T)/C_old(1)
C_old(T)/T
```

产物：

```text
results/c_old_cross_model_quant.csv
research/c_old_cross_model_quant.md
```

---

## Task C2：perf / cache counters

如果 perf 可用，测：

```text
cycles
instructions
cache-references
cache-misses
LLC-load-misses if available
mem-loads if available
```

如果硬件 perf 不支持 cache events，做 synthetic working set：

```text
vary rows / hidden / model-like weight size
force working set below/above cache levels
observe C(T) slope changes
```

产物：

```text
results/cache_counter_or_synthetic.csv
research/cache_effect_analysis.md
```

### C Go/No-Go

```text
GO-cache-characterization:
  C(T) slope changes significantly with model/quant/working-set,
  and the change correlates with cache/memory counters
  or synthetic cache-size sweep.

CONDITIONAL:
  weak slope changes but no clear counter evidence.

NO-GO:
  C(T) near-linear across all quant/model/working-set,
  and no cache-related explanation emerges.
```

如果 C GO，但 A/B NO-GO，可以写一个 measurement / negative-result style paper。
如果 C NO-GO，cache-aware 也不要继续。

---

# Part D：controller 只在 A 或 B 成功后做

现在明确禁止 agent 先做 controller。只有下面条件满足才进入 D：

```text
A4 GO/STRONG GO
or
B2 GO
```

然后才测：

```text
C_draft(d)
acceptance(d)
end-to-end speculation
```

## Task D1：测 C_draft 和 acceptance

先测 cheap draft：

```text
ngram-simple
ngram-map
ngram-mod
```

再可选：

```text
small draft model
```

workload：

```text
chat / random QA
code completion / code refactor
RAG template
structured output
reasoning-style long output
```

d：

```text
d ∈ {1,3,7,15}
T = 1+d
```

产物：

```text
results/draft_cost_acceptance.csv
research/draft_cost_acceptance.md
```

## Task D2：预测收益

用：

```text
J(d) = [C_verify(1+d) + C_draft(d)] / [1 + E_accept(d)]
```

报告：

```text
best_d per workload
best_d per curve/kernel
expected speedup vs d=0
expected speedup vs fixed d
```

### D Go/No-Go

```text
GO-controller:
  at least two workloads have different optimal d,
  and predicted speedup >= 1.15× in at least two workloads,
  and low-acceptance workload selects d=0 or d=1.

CONDITIONAL:
  one workload has predicted speedup 1.05×~1.15×.

NO-GO:
  all d have J(d) >= J(0),
  or one fixed d matches oracle within 3% across workloads.
```

---

# Part E：最终实验结论模板

让 agent 完成后必须用这个模板回答，不要自由发挥。

```text
Final Go/No-Go Summary

A. Curve-shaping kernel:
  status: STRONG GO / GO / CONDITIONAL / NO-GO
  key evidence:
    C_old_T4 =
    C_best_T1 =
    C_candidate_T4_total =
    speedup_vs_old_T4 =
    curve_ratio =
  interpretation:

B. Schedule variant crossover:
  status: GO / CONDITIONAL / NO-GO
  key evidence:
    number_of_variants =
    best_static_latency =
    best_dynamic_latency =
    dynamic_gain =
    crossover_observed = yes/no
  interpretation:

C. Cache-aware characterization:
  status: GO / CONDITIONAL / NO-GO
  key evidence:
    slope_changes =
    cache_counter_correlation =
    synthetic_cache_cliff =
  interpretation:

D. Controller readiness:
  status: READY / NOT READY
  reason:
    either no C_new(T), no variant crossover, no draft benefit, or ready.

Recommended next research direction:
  1. Continue VeriCurve-RV system
  2. Pivot to Schedule-at-Inference-Time
  3. Pivot to cache/measurement paper
  4. Stop this line
```

---

# 我对现在最可能结果的预判

基于你已经得到的 direct T4 失败，我认为最可能出现三种情况：

## 情况 1：R×T + packing 能把 T4 压下来

如果 A4 GO，那么继续 VeriCurve-RV。最终论文就是：

> **Curve-Shaping Verifier Microkernels for RISC-V Speculative Inference**

controller 是后半段，不是主贡献。

## 情况 2：R×T 也压不下来，但 schedule variants 有 crossover

如果 A NO-GO、B GO，那么 pivot 到：

> **Schedule-at-Inference-Time: Batch-Conditioned Kernel Variant Selection for RISC-V LLM Inference**

这个方向和 IntentIR/TianchenRV 的博士主线更强相关。IntentIR 已经证明 source schedule 不应被冻结，Layer C 可以作为 retuning hint，RVV 后端也已有 retuning收益。

## 情况 3：A/B 都 NO-GO，但 cache characterization 有结构

如果 C GO，那么做 measurement paper：

> **Why Batch Amortization Fails on RISC-V LLM Inference**

这可能不如系统论文惊艳，但可以是一个 honest paper。

## 情况 4：A/B/C 都 NO-GO

那就停。这个课题线说明：

```text
当前 RISC-V/llama.cpp low-bit path 下，
token-width / speculation / cache / schedule variation 都没有足够 leverage。
```

这时第三课题要换方向，不要硬做 controller。

---

# 你可以直接发给 agent 的短版指令

```text
Create a new Trellis task:

06-17-post-direct-t4-go-nogo

Goal:
After direct R1T4 failed, determine whether VeriCurve-RV can continue via:
A) layout-aware R×T curve-shaping verifier microkernels,
B) schedule-variant crossover / runtime schedule selection,
C) cache-aware characterization,
or should be stopped.

Do not implement controller yet.

Tasks:
1. Audit existing repack/llamafile/tinyBLAS/RISC-V 16x1 paths and explain why they did not help T>1.
2. Build R×T microkernel benchmark matrix:
   R ∈ {1,2,4,8}, T ∈ {1,2,4,8};
   include R1T1, previous R1T4, R2T2, R2T4, R4T1, R4T2, R4T4.
3. Run layout ablations:
   no packing, packed RHS, row-blocked weights, both.
   Report packing cost separately and total cost.
4. Judge curve shaping using:
   C_candidate_T4_total / C_best_T1
   and C_candidate_T4_total / C_old_T4.
5. In parallel, construct schedule variants and measure T(variant,B).
   Determine whether variant crossover exists.
6. Run cache characterization across model/quant/T and perf/synthetic cache tests.
7. Produce final Go/No-Go summary with:
   A curve-shaping status,
   B schedule-variant status,
   C cache-characterization status,
   D controller readiness,
   and recommended next research direction.

Hard rule:
Do not proceed to speculation controller unless A or B is GO.
```

我的建议是：**现在不要让 agent “继续做系统”，而是让它做这个三分支 Go/No-Go。**
这次任务的目标不是得到 speedup，而是判断这条研究线到底应该走：

```text
VeriCurve microkernel-system
Schedule-at-Inference-Time
Cache characterization
Stop
```
