---
title: "guess-figure — 猜历史人物（V3 含 3 步 LLM pipeline + 题库 65 + 95.4% 质量）"
summary: "九步 AI 原生开发工作流连续三期端到端做出的公开上线 Web 游戏。V1（001，2 天）：50 人物 × 7 线索 + LLM 异称匹配；V2（002，1 长 session）：匿名 cookie 账号 + 双层限流 + LLM 成本兜底；V3（003，1 工作日）：3 步 LLM pipeline 重构（强 LLM 产画像 → flash 产线索 → judge 自动重试）+ 题库 50→65 + quality_check 95.4% 满分率 + ¥2.61 总成本。"
tech: ["SvelteKit 5", "Svelte 5 Runes", "TypeScript", "Cloudflare Pages", "Cloudflare Functions", "Cloudflare D1", "Cloudflare Workers KV", "HMAC-SHA256 Cookie", "gemini-3.1-flash-lite", "deepseek-v3.2", "Wikisource API", "Python", "Vitest"]
githubUrl: "https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure"
status: "active"
pubDate: 2026-05-26
featured: true
order: 2
---

## 项目背景

[guess-figure](https://guess-figure.pages.dev) 是 vibe-coding-lab 的第二个端到端实战项目。延续 personal-website 验证的九步工作流，这次目标更复杂 —— **公开上线的 Web 游戏**（含游戏交互 / 状态机 / 50 人题库 / 内容生产 pipeline / LLM 调用 / daily 时间机制 / 移动响应式），看 v1.2 工作流是否在更高复杂度上仍能成立。

**总跨度：2 天**（vs personal-website 的 3 天 — 第二次跑工作流明显提速）。

## 玩法

- **日常游戏**：从 50 个中国历史人物随机抽题
- **今日挑战**：全球同题 / 每日 1 次 / 可分享得分
- 系统按难度从难到易给出 5 条标准线索 + 可选 2 条求救线索
- 玩家自由输入答案 → 异称表精确匹配（"诸葛亮"="孔明"="卧龙"）→ 失败 fallback 到 LLM 模糊匹配
- 计分：标准猜中 100/80/60/40/20，求救猜中 10，放弃 0
- 答错自动消耗一条线索（Stage 8 SPEC v1.1 修订）

## 关键架构

- **前端密集 + 轻后端**：所有游戏逻辑跑在前端（状态机 / 计分 / localStorage），后端 CF Pages Functions 只做 2 件事 — LLM 模糊匹配代理 + daily 路由
- **题库即代码**：50 人物 × 7 线索 JSON-in-git（`src/lib/data/figures.json`），跟代码一起部署 / 增量加题 = git push
- **LLM 极简调用**：95% 玩家命中异称表无需 LLM；仅 5% 走 fallback（月成本 < $5）
- **内容生产 pipeline**：Python 脚本 — 维基中文 + Wikidata + 百度补盲 → LLM 加工 7 条线索 + 难度 + 异称 → 人工审核 → 入库

## Stage 3 prototype 的多模型 benchmark 救场

V1 内容生产模型选型走了一段弯路：grill-me 阶段锚定 DeepSeek V3，但云雾上没有这个模型，实际可用是 `deepseek-v4-pro` / `deepseek-v4-flash` —— 两者都是 reasoning model，在严格 JSON 输出任务上 60% 失败率。

如果硬上 V1，会发现"上线慢 + 不稳"才回头改。但 Stage 3 prototype 阶段写了一个 `benchmark_models.py`，一次并行测 6 个模型 + 4 维数据（时间 / token / 成本 / 质量），10 分钟内挑出 **gemini-3.1-flash-lite**（4 秒 / 5/5 质量 / $0.00141）。模型选型从"假设 + 上线后才知道"变成"实测 + 决策前定"。

## Stage 8 Human QA 抓到的 3 个隐蔽 bug

工作流 v1.2 加的 `verification-before-completion` skill 在 Stage 7→8 强制跑命令验证，直接抓到：

1. **`/api/daily` 返回 `day_index: -1`** — LAUNCH_DATE_UTC 写错 1 天，AI 通道（HTTP 200 + JSON 返回）看不出来，typical "字面 AC PASS / 行为 AC FAIL"
2. **LLM `reason` 字段在前端泄露答案** — 玩家输"诸葛亮"猜错时 LLM 友好地回复"诸葛亮与朱熹并非同一人物" → **暴露答案"朱熹"**。AI 默认 helpful 行为 vs 游戏对抗场景的信息泄露面冲突
3. **SPEC v1.0 → v1.1 行为修订** — 用户 Stage 8 提"答错应自动消耗一条线索"，减少试探薅羊毛，触发 SPEC 修订并实测通过

## 完整 artifact

从 brainstorm 到上线的全部 9+1 阶段 artifact（含 Stage 10 复盘）在 [仓库的 workflow 目录](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/001-guess-figure)。

第二次跑九步工作流的复盘见 [博客](/posts/guess-figure-retrospective/)。

---

## V2 更新（2026-05-25，002 任务）：账号 + 限流 + LLM 成本兜底

**任务规模与产出**：22 个 AC 全过 / 9 步工作流又走一遍（含 4 个 ★ 人工关卡）/ 单 session 推完 / 单测 66/66 pass / 4 次 `fix(TX):` 回路诚实记录。

**为什么做这一期**：V1 上线后意识到 `/api/check-answer` 无 server 缓存、无每日预算上限——脚本挂一夜可刷光预算。"账号"+"限流" 是钱袋子兜底的最低门槛。

### 关键架构（v1.0.1）

| 维度 | 方案 | 备注 |
|---|---|---|
| **账号** | 匿名持久 cookie + HMAC-SHA256 signed UUID + 滚动续期 365d | "完全可选"语境；不引入邮箱（推后续 — 004 候选） |
| **持久化** | Cloudflare D1（users + games 表）+ 2 个 KV namespaces | schema 预留后续邮箱任务字段（004 候选） |
| **限流主线 1** | Workers KV 计数器（按 IP / 按 user 日窗口） | CF Pages free plan 不支持 dashboard rate limit rules → SPEC v1.0.1 acknowledge，Q 计数器全量替代 |
| **限流主线 2 LLM 成本** | KV 缓存（key 含 figure_id + aliases_hash）+ 全局日预算 V=8000 + 单点上限 X=50 + degraded 模式 | Stage 3 Prototype 实测云雾 ¥0.000526/call → V 阈值 ¥4.2/天兜底 |
| **降级 UX** | 响应 `degraded:true / network_error:true` 三态字段；前端识别后**不消耗线索** | 防"配额触发误扣线索"的字面 PASS / 行为破洞 |

### 工作流摩擦点（给 v1.3 的输入）

V2 期间又抓到 5 个 production 部署的隐性陷阱：

1. **wrangler.toml 模式覆盖 dashboard env vars** — Pages 项目加 wrangler.toml 后 plain-text vars 被忽略，需走 `[vars]` 段或 `wrangler pages secret put`
2. **CF Workers fire-and-forget promise 在 response 后被 kill** — `cacheSet(...)` 没用 `platform.context.waitUntil()` 包裹时 KV write 永不真完成 → cache 永久不命中
3. **CF KV cacheTtl 60s negative cache** — read-after-write 在同一边缘内最多 60s 看到旧 null，"立即第二次"的 cache hit 测试方法不适用
4. **Git Bash 字符编码损坏 UTF-8 字面值** — bash 中文字面量在 Windows locale 下变乱码字节，需 base64 encode JSON payload + stdin pipe
5. **CF Pages free plan 不支持 dashboard Rate Limiting Rules** — SPEC v1.0 假设的 P 路径直接走不通，SPEC v1.0.1 patch acknowledge + Q 计数器单维度覆盖

### V2 单测覆盖（vitest 66/66 pass）

- `match-exact.test.ts` 9 — normalize / matchExactly 行为不退化
- `auth.test.ts` 12 — HMAC sign/verify / cookie 颁发 / D1 INSERT OR IGNORE 幂等 / secret 缺失抛 500
- `hooks.server.test.ts` 4 — 全局 `/api/*` 鉴权钩子 4 个分支
- `rate-limit.test.ts` 17 — 4 类 counter / failure open/close / 跨日切 / 隔离性
- `llm-cache.test.ts` 12 — cacheKey aliases-hash 隔离 / 顺序无关 / cache miss/hit / KV 失败 silent
- `check-answer-client.test.ts` 12 — 4 响应分支（correct/wrong/degraded/network_error）调用 game state 正确

### V2 完整 artifact

[`workflow/002-account-rate-limit/`](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/002-account-rate-limit) 含 SPEC v1.0.1 / Plan / 20 Tasks / Implementation / Stage 8 用户实测清单 / Stage 9 22 AC 满足核对表。

V2 全流程的工作流复盘见 [博客](/posts/guess-figure-002-account-rate-limit/)。

---

## V3 更新（2026-05-26，003 任务）：3 步 LLM pipeline + 题库 50→65 + 内容质量阶跃

**任务规模与产出**：18 AC（15 PASS + 3 偏差 explicit accept）/ 单工作日推完 / 123 测全 pass / 4 次 `fix(TX):` 回路诚实记录 / 总 LLM 成本 ¥2.61 / 0 commit 动过游戏机制（AC16 完美）。

**为什么做这一期**：V2 题库 50 个人物 × 7 线索的**内容质量本身**有天花板——乾隆 d1「十项武功」≈ alias「十全老人」(语义穿底)、关羽 d7「字云长」⊂ alias「关云长」(子串穿底)、刘备 d2「织席贩履 + 结义兄弟」（标志事件穿底）、乾隆 d5 比 d1 更易猜（梯度乱序）。**老 pipeline 单步 LLM + 1000 字摘要**信息饥饿,无法支撑梯度精细化。

### 关键架构（v1.1）

| 维度 | 方案 | 备注 |
|---|---|---|
| **3 步 LLM pipeline** | (强 LLM) 三源 → 8-section 画像 → (flash) 画像 + banlist + few-shot → 7 条 clues → (flash) judge 自动重试 N=2 | 强 LLM 主选 `deepseek-v3.2`(prototype 横向对比 haiku/gemini-pro-thinking-fail 后定);成本 ¥0.05/figure vs haiku ¥0.18 |
| **输入侧三源材料** | 维基中文全文 5000 字（原 1000 字摘要）+ Wikidata 6 字段 + 二十四史 Wikisource 选段 5000 字（按 mapping） | mapping 阿拉伯数字 fix 后 hit 率 80%+,拉不到走 fallback 仅维基+Wikidata |
| **数据资产化** | `src/lib/data/profiles/{id}.md` × 69 个 8-section markdown 入 git | 后续 006 / 新玩法（判断题/选择题）可复用同一份 profile |
| **quality_check 升级 4 项** | d1-5 不含 aliases ≥3 字子串 + d1-5 不含 profile typology banlist + 信息密度梯度启发式 + LLM-as-judge `--with-judge` flag | 最终 62/65 = **95.4%** 满分率（SPEC AC6 ≥ 90% 过） |
| **regression 兜底机制** | `regen_diff.py` 自动算 v1 vs v2 score（同一升级 quality_check）→ "候选采用 v2" 或 "保留 v1" → final figures.json 50 旧 = 31 v2 + 19 v1 混合 | 用户 T20 "全部按自动决策" 一句话通过,无逐 entry review |
| **强约束防御** | thinking model detect（`reasoning_tokens > 0 + content 空 → raise`）+ clue prompt inject banlist（5 好+5 坏 few-shot 随机选 1 对） | 防 gemini-2.5-pro 类静默失败 + 防 d4-5 banlist 失控 |

### 工作流摩擦点（给 v1.3 的输入）

V3 期间又抓到 5 个 LLM iteration 的隐性陷阱：

1. **LLM 静默改 figure name** — clues_obj.name 把"康熙"改成"康熙帝",production code 应 hardcode key field 而非取 LLM 输出
2. **profile aliases 长度直接 driver clue 触发率** — 乾隆 11+ aliases 让 d6/d7 几乎不可能 judge 通过,X 方案 `PROFILE_PROMPT` 限 aliases ≤ 5 才解决
3. **gemini-2.5-pro thinking model 输出空 content** — `completion_tokens=3997` 全在 `reasoning_tokens`,后续 pipeline 拿到空 profile 失败;call_llm 必须 detect
4. **Wikisource page name 格式漂移** — LLM 凭知识写"卷一上"中文数字,实际 Wikisource 用"卷1上"阿拉伯数字,T22 第 1 轮 0/20 全 fail;mapping 生成后必须 verify hit rate
5. **deterministic check 跟 LLM judge prompt 双重 standards** — check #6 ≥ 2 字 vs judge ≥ 3 字,quality_check 第 1 跑 42% 满分率,对齐后 95.4%

### prompt 调优 2 轮（X + Y 方案）

T14 灰度 5 figure 第 1 跑 4/5 fail。诊断 + 修 2 处:

- **X 方案**(治本):`PROFILE_PROMPT` 限 aliases section ≤ 5 个最常用,排除 ≥ 10 字完整谥号
- **Y 方案**(止损):`JUDGE_PROMPT` 子串规则 ≥ 2 字 → ≥ 3 字,d6/d7 整字 alias 改"可疑"(求救范围允许暴露)

第 2 跑 4/5 通过(关羽/刘备/李白/苏轼;乾隆仍 fail —— alias「十全老人」典故「十全武功」太著名 LLM 在 d1-5 难避开 systematic hard case)。

### 65/70 偏差 + 用户 explicit accept

50 旧 figure 跑出 14 failed + 20 新皇帝跑出 5 failed = 19 failed(SPEC AC9 ≤ 5 字面违反 ≥ 4 倍)。但:**50 旧有 v1 fallback,5 新无 fallback 即 AC3 偏差**(题库 65/70)。

**用户在中途多次 explicit accept**(T15 "A 接受 65 GO" + T20 "全部按自动" + Stage 8 "通过"),最终 figures.json 65/70 entry 上线。**workflow 灵活性证据**:SPEC AC 字面违反 vs spirit 用户知情同意,Stage 9 sign-off 通过。

### V3 测试覆盖（123/123 全 pass）

- `vitest` **66/66**（含 002 的 54 测 + V3 期间游戏端继承的 12 新测）
- `quality_check.py` Python `unittest` **39/39**（helper / check #6/7/8 / stopword / mock LLM judge / 旧 5 项回归）
- `generate_figures.py` Python `unittest` **18/18**（call_llm thinking 防御 / validate_profile_sections / material_to_text / parse_json / estimate_cost / clues banlist inject / judge retry loop）

### V3 完整 artifact

[`workflow/003-clue-optimization/`](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/003-clue-optimization) 含 SPEC v1.0/v1.0.1/v1.1 / 26 Tasks / Implementation / Stage 8 入场报告 / Stage 9 18 AC 核对表 / `spec-emperor-list.md` 20 皇帝候选清单 / `proto/` 多模型横向对比 spike 数据。

V3 全流程的工作流复盘见 [博客](/posts/guess-figure-003-clue-optimization/)。
