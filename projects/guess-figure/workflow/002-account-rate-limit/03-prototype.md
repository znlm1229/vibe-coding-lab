# Stage 3 ｜ Prototype 原型

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-3--prototype-原型)
>
> **要点**：解决最大不确定性；最小可运行；用完即弃；**当无真正不确定性时直接跳过**。

## 决定

- [x] **构建原型** — 解决的不确定性：**云雾中转 gemini-3.1-flash-lite 单次调用真实成本**与**实际延迟分布**。Stage 2 Grill Q11 锁定本阶段只做这一件事，回填 SPEC 的 V (日全局 LLM 预算) 与 X (单 user 日 LLM 上限) 阈值。

## 原型位置

- 脚本：[`scripts/measure_llm_cost.py`](../../scripts/measure_llm_cost.py)
- 实测原始记录：`scripts/logs/llm_cost_20260522_175826.json`（gitignore，不入仓库；100 次调用的逐次 latency + token + content_snippet）
- Sanity check 记录（先跑 5 次验证脚本）：`scripts/logs/llm_cost_20260522_175544.json`

跑法：

```bash
cd projects/guess-figure
source venv/Scripts/activate
python scripts/measure_llm_cost.py --count 100 --daily-budget-yuan 5
```

脚本特点（与 `/api/check-answer` 端点对齐保证测量代表性）：

- `model = gemini-3.1-flash-lite`、`max_tokens = 300`、`temperature = 0.1`、`timeout = 10s` —— 全部与 [check-answer/+server.ts:54-67](../../src/routes/api/check-answer/+server.ts) 一致
- prompt 字符级复用 [check-answer/+server.ts:34-50](../../src/routes/api/check-answer/+server.ts) 的模板
- 100 次构造 `(figure, guess)` 测试对：从题库 50 figures × 取姓 + 称谓后缀（"老丞相 / 应该是陶先生 / 司陛下"）→ 强制 LLM 介入而非 client `match-exact` 短路
- 随机种子 42 固定，结果可复现
- 串行调用（避免触发云雾自身限流）

## 验证 / 证伪了什么

### 实测结果（2026-05-22 17:58, 100 次调用）

| 指标 | 实测值 | 备注 |
|---|---|---|
| 调用次数 | 100（95 成功 + 5 失败） | 失败率 5% |
| 总耗时 | 366 秒 (~6 分钟) | 串行 |
| 平均延迟 | 3276 ms | |
| **p95 延迟** | **7856 ms** | 接近 10s timeout 门 |
| Prompt tokens 累计 | 22380 | 均值 235.6/次 |
| Completion tokens 累计 | 3652 | 均值 38.4/次 |
| Total tokens 累计 | 26032 | 均值 274.0/次 |
| **云雾账户实测扣费** | **¥0.05**（实测前后余额差） | 用户手工读 console |

### 单次调用真实成本

- **¥0.05 / 95 成功 ≈ ¥0.000526/次** —— 约 0.05 分/次
- 比 brainstorm 阶段占位估算（¥0.001/次）**便宜约一半** —— grill Q11 出来的最大未知数被解开，**比预期乐观**

### 5 次失败全部同型

100 次中 5 次失败的错误类型：

```
all five errors: network: HTTPSConnectionPool(host='yunwu.ai', port=443):
  Read timed out. (read timeout=10)
```

100% 都是 **10 秒 ReadTimeout**。**单一失败模式**——没有 HTTP error / JSON parse error / 鉴权错误等其他类型。与 p95 = 7.8 秒数据一致：约 5% 请求超 10 秒。

### 验证的事

- ✅ 云雾中转 gemini-3.1-flash-lite 计费极低（< 0.1 分/次）—— 钱袋子风险被实测压缩
- ✅ token 用量稳定（prompt 230-236 tokens 几乎无方差；completion 30-50 tokens）——便于精确预算
- ✅ 95% 调用在 < 8 秒完成，平均 3.3 秒 —— 合理 UX
- ✅ 脚本本身的 prompt 形态与生产端点一致 —— 实测代表性强

### 证伪 / 推翻的假设

- ❌ Brainstorm 阶段占位的"单次约 ¥0.001"被证伪，实际仅 ¥0.000526
- ❌ Grill Q6 的占位 V=5000/日（对应 ¥5 容忍）需要上调到 8000-10000/日
- ❌ "失败率 < 1%"的隐含假设被证伪——**实测 5% 失败率，必须进 SPEC**

## 对 SPEC 的影响

### 已可定的阈值（SPEC 阶段直接采用）

| OQ | brainstorm 占位 | 实测后建议 | 公式 |
|---|---|---|---|
| OQ1 LLM 单次成本 | ¥0.001（猜） | **¥0.000526**（实测） | ¥0.05 / 95 |
| OQ2 V 日全局 LLM 预算 | 5000/日 | **8000/日** | ¥5 / ¥0.000526 ≈ 9500，留 buffer 取 8000 |
| OQ3 X 单 user 日上限 | 30/日 | **50/日** | 重度合法玩家 30 × 2 倍 buffer = 60，向下取 50；远小于 V/100=80 更稳 |

阈值仍**写到 env vars 可调**，不硬编码：
- `LLM_BUDGET_DAILY=8000`
- `LLM_BUDGET_PER_USER=50`
- 后续观测真实流量再微调

### 新增 SPEC 必须处理的约束（grill 未料到）

1. **5% LLM 失败率必须区分于"判 false"**。SPEC 必须显式：
   - LLM 网络/超时错误 → 响应 `{ok: false, reason: "AI 响应异常，请稍后重试", network_error: true}`（**与降级模式 `degraded: true` 不同字段**，便于前端独立处理）
   - 前端 `check-answer-client.ts` 见 `network_error: true` 时：**不消耗线索**（与 Q7 降级模式行为一致）+ 提示用户重试
   - SPEC 必须有一条 AC 专门验证此分支

2. **P95 延迟 7.8s → UI loading state 必须明显**。SPEC 必须：
   - 前端在 > 1s 后显示"AI 裁判中..."占位（避免用户以为卡死）
   - 在 > 5s 后显示更明显的进度提示
   - 已 acceptance test 必须含"模拟慢响应"的 case

3. **timeout 阈值保留 10 秒**。LLM_TIMEOUT_SEC 不变；提高到 15s 可降失败率到 ~1-2% 但用户等待时间损失更大，不划算。

### Stage 4 SPEC 不再需要等待的 OQ

- OQ1 / OQ2 / OQ3 全部回填完成 → SPEC 可写"已定数字 + env vars 可调"
- OQ7 (`/api/me` 仅汇总) / OQ8 (`/api/me` cache 策略) 已在 grill 中拍板推荐 → SPEC 直接采用
- 剩 OQ4 (P dashboard 规则集) / OQ5 (降级文案，taste) / OQ6 (cookie maxAge) 三项 SPEC 阶段决

### 仍留观测的 OQ

- **真实命中率**（U 的 60-80% 假设）—— 上线后 1-2 周看 KV stats
- **真实重度玩家用量**—— 上线后看 D1 games 表分布；X=50 是否合理需复盘
- **云雾计费稳定性**—— 100 次实测期 ¥0.05 是**单点观测**，云雾计费策略变更需重新校准
