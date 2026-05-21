# Stage 2 ｜ Grill Me 质询拷问

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-2--grill-me-质询拷问)
>
> **强制工具**：调用 `grill-me` skill 驱动本阶段（v1.1+）。skill 会逐条审问用户的方案 / 设计，覆盖决策树的每个分支。AI 自由列几个问题不能替代。skill 不可用时停下来告诉用户，不要静默退化。
>
> **要点**：暴露隐藏假设、边界、失败模式、集成风险；每条具体到可执行（不写「考虑过边界情况了吗？」这种废话）。

## Skill 调用记录

- **Skill**：`grill-me`（located at `C:\Users\61780\.claude\skills\grill-me`）
- **调用时间**：2026-05-21
- **交互轮数**：10 个主问题 + 2 个 follow-up（求救机制 7b、后端拷问 9b）= 12 轮
- **覆盖的关键决策分支**：
  - 1. 题库规模 + 覆盖范围
  - 2. 内容生产 pipeline 选型（爬虫 vs LLM 生成 vs 手写）
  - 3. 爬虫源选择 + 合规性
  - 4. 线索数量 + 难度分级方式 + 展示次序
  - 5. 自由输入容错策略 + LLM 调用频率 + 成本估算
  - 6. Daily 模式 V1 范围 + 4 项参数（时区/限次/分享/历史回看）
  - 7. 失败 / 放弃路径 + 求救线索机制 + 计分公式
  - 8. 反作弊机制 + 排行榜 V1 范围
  - 9. 技术栈 + 后端架构 + 题库存储 + 增量机制
  - 10. V1 范围最终收敛
- **被搁置的分支与理由**：
  - 国际化 / 英文版 — 理由：用户未提；中文用户为主，V1 不必，可能永久不做
  - 玩家社群 / 评论 / UGC — 理由：超 V1 范围；账号系统都没有，社群建在沙上
  - 付费 / 商业化 — 理由：V1 目标是验证产品，不商业化

## 拷问对象

来自 Stage 1 [01-brainstorm.md](./01-brainstorm.md) 用户选定的**方向 B + D 合并形态**：

- **底层玩法（B）**：AI 按难度从难到易给若干条线索；玩家随时输入答案；越早答中分越高；输入用 LLM 模糊匹配处理异称
- **内容投放变体（D）**：每日一题模式 — 全球同题、24 小时新换、玩家分享分数

拷问目标：把"概念方向"压力测试到 V1 可上线集合 + SPEC 阶段所需 OQ。

## 拷问决策记录

> 每项格式：**问题 → AI 推荐 + 理由 → 用户决定 → 含义**

### 决策 1 — 题库规模 + 覆盖范围

- **问题**：V1 题库初始多少人、覆盖什么范围？
- **AI 推荐**：50 人 + 中国史。理由：V1 最快上线；LLM 中文知识对中国史最准；数据源稳；daily 模式可跑 ~50 天
- **用户决定**：✅ 接受
- **含义**：内容生产工作量 ≈ 50 人 × 5 标准线索 = 250 条标准内容（升级到 7 条后 = 350 条）；daily 模式 50 天耗一轮

### 决策 2 — 内容生产 pipeline

- **问题**：50 人中国史的题库怎么生产？
- **AI 推荐**：LLM 批量生成 + 你抽检 + 静态 JSON（最轻）
- **用户决定**：**爬虫为主 + LLM 二次加工**（推翻 AI 推荐）
- **含义**：V1 工程量 +1 周（要做爬虫脚本 + LLM 加工脚本），但事实准确性比纯 LLM 生成高。生产 pipeline 流程：爬虫拉结构化字段 → LLM 重写成 7 条线索（按难度排）→ 你审核

### 决策 3 — 爬虫源

- **问题**：50 人中国史的结构化字段从哪里爬？
- **AI 推荐**：维基中文 + Wikidata（自动）+ 百度百科手动补盲
- **用户决定**：**维基 + Wikidata + 百度百科爬虫补充**（接受主源 + 升级补充策略：百度也用爬虫，但定位为"补充"非"主源"）
- **含义**：技术细节：
  - 主源自动：维基中文用 MediaWiki API（`wikipedia` 或 `wikipediaapi` Python 库）；Wikidata 用 SPARQL `wbgetentities`
  - 补充源百度百科：仅针对维基资料不足的 ~10-20 人；低频访问（≥ 1s 间隔）；UA 模拟浏览器；接受合规边缘风险（50 人小样本）
  - 每条线索标 `source` 字段（"wikipedia" / "baidu" / "manual"）便于追溯准确性

### 决策 4 — 线索数量 + 难度 + 次序

- **问题**：每题多少条线索 / 谁标难度 / 怎么展示？
- **AI 推荐**：5 条 + LLM 标难度（生产时一并标）+ 从难到易展示
- **用户决定**：✅ 接受
- **含义**：但后续决策 7 升级到 7 条（5 标准 + 2 求救）

### 决策 5 — 自由输入容错策略

- **问题**：玩家输入怎么判定对错？LLM 调用频率？
- **AI 推荐**：两段式 = 异称表精确匹配（命中 95%，无 LLM）+ LLM fallback（5%）+ 错字不容忍
- **用户决定**：✅ 接受
- **含义**：
  - 精确匹配预处理：去空格 / 繁→简 / 全→半角 / 去标点
  - 异称表覆盖：本名 + 字 + 号 + 谥号 + 庙号 + 别号（每人物 3-5 个）
  - LLM 模型：**DeepSeek V3**（通过云雾 OpenAI-compatible 中转；中文 NER 中国历史人物训练充分）
  - 月成本估算（10 万 MAU 假设）：~3.75 万次 LLM 调用 × ~$0.00002 ≈ **$0.8-1/月**（DeepSeek V3 比 DeepSeek V3 便宜 4-5 倍）
  - 边界规则：仅姓氏 / 仅名 / 错别字 → **不算对**

### 决策 6 — Daily 模式 V1 范围 + 4 项参数

- **问题**：daily V1 必做 / V2 再加？参数怎么定？
- **AI 推荐**：V1 必做 daily + 默认值：北京 0:00 换题 / 限 1 次/天 / 文字 emoji 分享 / 无历史回看
- **用户决定**：✅ 接受
- **含义**：
  - 后端 daily 路由按 UTC 16:00 切换（= 北京 0:00）
  - localStorage 防同浏览器复玩
  - 分享格式：`猜历史人物 #51 ❓❓❓✅ 用了 3 条线索 https://<domain>`
  - 错过当天 = 错过（不做历史回看，V2 加）

### 决策 7 — 失败 / 放弃路径

- **问题**：5 条线索用完没猜中 / 玩家想放弃怎么处理？
- **AI 推荐**：自动显示答案 + 随时可放弃 + 不锁
- **用户决定**：**可以再给 2 条线索 + 可以随时放弃**（推翻"5 条" 设定，新增求救机制）
- **含义**：触发 follow-up 决策 7b

### 决策 7b（follow-up）— 求救线索的产生方式 + 计分

- **问题**：求救的 2 条线索预生成还是 LLM 实时？计分如何？
- **AI 推荐**：预生成 + 求救模式 10 分 + 放弃 0 分
- **用户决定**：✅ 接受
- **含义**：
  - 题库 schema 升级：每人物 = 7 条线索（难度 1-7，前 5 标准、后 2 求救）
  - 计分公式：
    | 用了几条 | 标准 1 | 2 | 3 | 4 | 5 | 求救 6 | 7 | 放弃 / 失败 |
    |---|---|---|---|---|---|---|---|---|
    | 得分 | 100 | 80 | 60 | 40 | 20 | 10 | 10 | 0 |
  - daily 分享 emoji：✅（标准猜中）/ 🆘（求救猜中）/ ❌（放弃或 7 条用完）
  - LLM 加工 prompt 要相应调整：一次产 7 条而非 5 条，前 5 严格"从难到易"，后 2 是"接近暴露答案"

### 决策 8 — 反作弊 + 排行榜

- **问题**：daily 反作弊到什么程度？V1 要不要排行榜？
- **AI 推荐**：1 级 localStorage 防复玩 + V1 无排行榜
- **用户决定**：✅ 接受
- **含义**：
  - V1 无账号系统
  - localStorage key 例：`daily_played_20260521 = true`
  - 已玩当天 → 入口显示"今日已完成：X 分"+ 分享按钮 + 倒计时下题
  - **接受软漏洞**：换浏览器 / 隐身模式 / 清缓存能刷 → V1 不堵
  - V2 加账号系统时一并加排行榜

### 决策 9 — 技术栈

- **问题**：V1 用什么技术栈？
- **AI 推荐**：Astro + React island + CF Pages + CF Workers + Haiku（复用 personal-website 经验）
- **用户决定**：**SvelteKit + CF Pages + CF Pages Functions + DeepSeek V3（通过云雾中转）**（推翻"复用 Astro"建议；用户选择新栈 + 后续指定云雾代理 + DeepSeek 模型）
- **含义**：
  - 用户没 SvelteKit 经验，学习曲线计入项目时间但不计入工程估算
  - SvelteKit 部署用 `@sveltejs/adapter-cloudflare`（专为 CF Pages 设计）
  - 游戏状态用 Svelte 5 runes（`$state`、`$derived`、`$effect`）
  - 触发 follow-up 决策 9b（后端架构澄清）

### 决策 9b（follow-up）— 后端架构 + 题库存储 + 增量机制

- **用户疑问**："不接 DB 怎么存储题库？怎么增量添加？"
- **AI 澄清**：方案不是"纯前端"，是"前端 + 2 个 serverless edge function（CF Pages Functions = CF Workers 简化版）"
- **用户决定**：**A — JSON-in-git + 增量脚本**（保持轻后端 + 不上 DB）
- **含义**：
  - **题库存储**：`src/lib/data/figures.json`（跟代码一起 commit）
    - 格式（JSON）：
      ```json
      [
        {
          "id": "zhuge-liang",
          "name": "诸葛亮",
          "aliases": ["孔明", "诸葛孔明", "卧龙", "武侯"],
          "clues": [
            {"text": "<最难线索>", "difficulty": 1},
            {"text": "...", "difficulty": 2},
            {"text": "...", "difficulty": 3},
            {"text": "...", "difficulty": 4},
            {"text": "<标准范围内最易>", "difficulty": 5},
            {"text": "<求救线索 1>", "difficulty": 6},
            {"text": "<几乎暴露答案>", "difficulty": 7}
          ],
          "source": "wikipedia",
          "wiki_url": "https://zh.wikipedia.org/wiki/诸葛亮"
        }
      ]
      ```
    - 大小估算：50 人 × 7 条线索 × ~80 字 ≈ 50-80 KB
  - **增量流程**：
    1. `python scripts/generate_figures.py --new-batch 10` → 选 10 个新人物 → 爬虫 → LLM 加工 → 输出 `figures-new.json`
    2. 你 review 这 10 人（VS Code 看 JSON，改错的事实）
    3. `python scripts/merge.py figures-new.json` → 合并入主题库（去重 + 按 id 排序）
    4. `git commit -m "task-TX: 题库 +10 人物" && git push`
    5. CF Pages auto build & deploy（~30 秒）→ 用户下次刷新看到新题
  - **轻后端 2 个 SvelteKit `+server.ts` endpoint**：
    - `src/routes/api/check-answer/+server.ts` → POST → 接收 `{figure_id, user_input}` → 异称表预匹配（命中直返）→ 调 DeepSeek V3 API（带 figure 上下文）→ 返回 `{correct: bool, reason?: string}`
    - `src/routes/api/daily/+server.ts` → GET → 按 UTC 16:00 切换 → 返回 `{figure_id, date}`（不返回题库内容，前端再查 JSON）
  - **为什么不上 DB**：V1 无账号 / 无成绩持久化 / 无排行榜 → 用户数据为 0；题库 50 人 = JSON 完美；上 DB 是过度设计

### 决策 10 — V1 范围最终收敛

- **用户决定**：✅ 接受 V1 清单（见下节"V1 范围"）
- **含义**：grill-me 收敛，进入 02-grill-me artifact 写作 → 用户 review → 进 Stage 3 决策（是否需要 prototype）

## V1 范围（grill-me 输出契约）

> **此节是 Stage 4 SPEC 的输入起点**。SPEC 阶段把这里的范围具化为可测试 AC + Behavior + Constraints。

### V1 必做集合

| 类别 | 必做项 | 工程量 |
|---|---|---|
| **内容 pipeline** | `scripts/generate_figures.py`（维基中文 + Wikidata 主源 / 百度百科补充 / DeepSeek V3 加工 / 输出 JSON）+ `scripts/merge.py`（增量合并）+ 你审 50 人 | ~3 天 |
| **题库产物** | `src/lib/data/figures.json` — 50 人 × {id, name, aliases[3-5], clues[7]{text, difficulty 1-7}, source, wiki_url} | — |
| **前端** | SvelteKit 5 + adapter-cloudflare：首页（日常 / daily 双入口）/ 日常游戏页（线索逐条 + 输入框 + 求救按钮 + 计分 + 失败显示）/ daily 页（今日题 + localStorage 防复玩 + 分享按钮）/ 移动响应式 | ~6 天 |
| **轻后端** | 2 个 `+server.ts`：`/api/check-answer`（异称表 + LLM 代理）+ `/api/daily`（今日题路由）+ rate limit + 异常处理 | ~2 天 |
| **部署** | CF Pages 自动 deploy + `.pages.dev` 子域名 + CF AI Gateway 监控 LLM 调用 | ~2 天 |
| **QA + 调优** | 移动端 / 多浏览器 / LLM 边界用例 / 题库错误抽查 / 移动端中文 IME | ~3 天 |

**V1 总工时估算：~16 工作日（SvelteKit 学习时间另算）**

### V1 明示不做（避免 SPEC 阶段重新议论）

| ❌ 不做项 | 原因 / 何时做 |
|---|---|
| 账号系统 | V2 — 当排行榜成为需求时一起做 |
| 排行榜 | V2 — 跟账号绑 |
| daily 历史回看 | V2 — 增加路由 + 反作弊复杂度 |
| 题库管理后台 | V2 / 可能永不做 — V1 直接 JSON commit |
| 用户报错通道 | V2 — 加简单 `mailto:` link |
| 多语言 / 英文版 | 可能永不做 — 中文用户为主 |
| 自定义域名 | V1 用 `.pages.dev`；品牌化可单独开任务 |
| 用户提交人物 / UGC | 可能永不做 |
| 排行榜社交功能 | V2 后期 |
| 付费 / 订阅 | 不在视野 |

## 高危风险（SPEC / Prototype 阶段必须解决）

- [ ] **题库 LLM 加工质量不可控**：DeepSeek V3 加工 7 条线索时可能：(a) 事实错误（年份 / 官职 / 籍贯偏差）；(b) 难度排序失误（第 1 条不是最难）；(c) 异称遗漏（漏列"孔明"导致玩家输孔明被判错）。人工审核 50 人能否拦住所有这些？**建议 Stage 3 做 prototype**：拿 5-10 个代表人物完整跑一遍 pipeline，看输出质量决定是否调 prompt 或加自动校验脚本
- [ ] **daily 内容耗尽降级方案缺失**：50 天后 daily 题库每天必有 1 题，第 51 天怎么办？目前没决策。**SPEC 必须明确**：(a) 第 51 天起 daily 进入"轮播第 1 题"；(b) 第 30 天起强制内容生产新批；(c) daily 题用过即"用尽"，第 51 天显示"今日休息"等。不能默认"50 天内必把新题加进去"
- [ ] **LLM API 速率限制**：DeepSeek V3 默认 API 速率上限？10 万 MAU 假设下高峰期是否会 throttle？**SPEC 必须查 Anthropic 当前 rate limit 文档 + 明确超限降级策略**（排队？返回错误让前端 fallback 到字符串匹配？）
- [ ] **SvelteKit + CF Pages + Workers 部署链路用户没用过**：跟 personal-website 的 Astro + CF Pages 链路不同（adapter 配置 / `+server.ts` runtime / 环境变量注入方式都不一样）。**Stage 3 prototype 必须包含"hello world endpoint 部署到 CF Pages 成功 + 能调通 Claude API"**，否则 V1 末期才发现部署坑就晚了

## 中危风险

- [ ] 异称表穷举度不足导致 LLM fallback 频次过高 → 月成本超预算（$4 → $20+）。**SPEC AC 应包含"95% 玩家输入命中异称表"作为可测量指标**
- [ ] 移动端中文 IME 与 onSubmit 时机冲突（玩家按"完成"键时输入法仍未确认 → 提交空串）。**SPEC 必须包含 IME composition 事件处理 + Stage 8 必须真机测**
- [ ] 玩家"换浏览器刷 daily"反作弊漏洞被某些社交圈滥用 → daily 分享变成"晒重玩成绩"失去意义。**SPEC 明示接受此漏洞，Stage 9 验收时不当作 bug**
- [ ] SEO：daily 页面（`/daily`）是否需要 prerender / 静态化以便分享到微信 / 朋友圈时显示卡片？**SPEC 必须明确 daily 页面 SSR vs CSR + Open Graph meta 标签策略**
- [ ] 爬虫源稳定性：维基中文 / 百度百科版面变更 / robots.txt 调整可能导致脚本失败。**SPEC 应明确"爬虫脚本是 best effort 工具，失败 fallback 到人工补"**

## 低危 / 已知妥协

- [ ] 不支持账号 / 排行榜（V1 明示）
- [ ] 不支持 daily 历史回看
- [ ] 仅中文，不支持多语言
- [ ] 题库 = 50 人，频繁玩家 1-2 周可全猜过
- [ ] 题库 JSON 打包进 bundle = 全量下载到客户端，玩家用浏览器 dev tools 能"作弊"看答案。V1 不堵（小项目，作弊者自损游戏体验，不影响诚实玩家）

## 待用户回答的开放问题（OQ）

> 这些是 grill-me 没拍板、留给 Stage 4 SPEC 阶段定的细节。**每条 OQ 必须标 type**（v1.2+）：

| # | 问题 | 类型 | AI 推荐 | 决定 | 备注 |
|---|---|---|---|---|---|
| OQ1 | daily 第 51 天起怎么办（题库耗尽降级）？ | technical | 第 51 天起 daily 进入"轮播第 1 题"，前端显示"今日：经典回顾 第 N 周"；同时提示用户日常模式有同样题。配套：第 40 天起脚本自动提醒你"该补题了" | (待) | 直接影响 SPEC Behavior |
| OQ2 | 50 人具体名单怎么定？ | technical | LLM 列 100 个候选 → 你筛 50 → 平衡：朝代分布（先秦 / 汉 / 唐 / 宋 / 明清 / 近代 各 8-10 人）+ 类型分布（帝王 / 军政 / 文学 / 思想家 / 科技 各 8-12 人）+ 知名度分布（一线人物 30 + 二线 15 + 冷门 5） | (待) | SPEC 阶段或 Stage 7 实施前定 |
| OQ3 | LLM 模糊匹配 prompt 完整版定稿 | technical | 见决策 5 草案；SPEC 阶段加边界用例测试集（30-50 用例）finalize | (待) | SPEC AC 应含 prompt + 用例集 |
| OQ4 | daily 题选择策略（按入库顺序 / 难度均衡 / 手动指定）？ | technical | 按入库顺序（最简）；V2 加"难度均衡算法"（保证连续 7 天不会全是冷门 / 全是大众） | (待) | SPEC 写明确 |
| OQ5 | 失败显示答案后人物简介长度？ | technical | 一句话 + 维基百科链接（V1 极简）；V2 可考虑小卡片（含画像 / 生卒 / 一两句生平） | (待) | SPEC 写 UI 详 |
| OQ6 | LLM 模型最终选哪个？API 提供商？ | technical | Stage 2 末初选 DeepSeek V3；Prototype A 实测后修订为 **gemini-3.1-flash-lite** | ✅ **已定 gemini-3.1-flash-lite via 云雾**（Stage 3 Prototype A 实测后修订）| Prototype A 6 模型基准 + 2 模型 × 5 人物全量验证：gemini 4 维领先（4s/$0.00141/质量5/5/成功率5/5）；deepseek-v4-flash 60% 失败率被淘汰；reasoning model 不适合 V1 任何场景。详细见 [`03-prototype.md`](./03-prototype.md)（待写）|
| OQ7 | 部署的 pages.dev 子域名？ | taste ⚠️ | `guess-figure.pages.dev`（直白匹配项目名）；或 `lw-figure.pages.dev`（沿用 personal-website 的 `lw-` 前缀作为个人项目命名习惯） | (待) | **AI 起草仅占位，用户应自己改** |
| OQ8 | 项目品牌名（中文）？ | taste ⚠️ | "猜历史人物"（直白）/ "他是谁"（悬念）/ "古今谁人"（文艺）— 各占位草稿 | (待) | **AI 起草仅占位，用户应自己改** |
| OQ9 | 主色 / 视觉风格 | taste ⚠️ | 极简（白底黑字 + 一色强调，类似 Wordle）/ 中国风（米色底 + 朱砂红 + 古风字体）/ 卡牌风（每条线索一张卡片）— 三种占位草稿 | (待) | **AI 起草仅占位，用户应自己改** |
| OQ10 | 分享文案 emoji 风格 | taste ⚠️ | 见决策 7b 草案；正式上线前你定 | (待) | **AI 起草仅占位，用户应自己改** |
| OQ11 | 首页文案 / Hero | taste ⚠️ | "猜历史人物 — 5 条线索，你能猜出他是谁？" — 占位 | (待) | **AI 起草仅占位，用户应自己改** |
| OQ12 | 移动端布局风格（垂直流 / 卡片栈 / 水平滑动）？ | taste ⚠️ | 垂直流（最自然，符合 Web 直觉）；卡片栈适合"线索一张一张展示"的仪式感；用户决定 | (待) | **AI 起草仅占位，用户应自己改** |

## 用户可接受暂时搁置的问题

- [ ] 国际化 / 英文版（中文用户为主，可能永不做）
- [ ] 玩家社群 / 评论 / UGC（账号都没有，超 V1）
- [ ] 付费 / 商业化（V1 验证产品为先）
- [ ] 移动端 PWA（V1 仅响应式 Web，PWA 是 V2/V3 增项）
- [ ] LLM 模型多家比对（V1 锁 Claude；V2 可考虑 Gemini Flash / GPT-4o-mini 备选 + AI Gateway 路由）

---

## 下一步建议

按 workflow-spec：

- **Stage 3 Prototype 是否需要做**？根据高危风险清单，**强烈建议做 prototype**（≤ 1 天）覆盖两个最大风险：
  1. **内容 pipeline 端到端跑通 5 个人物**（验证 LLM 加工质量是否人工审核能拦住）
  2. **SvelteKit + CF Pages + Worker 部署 + 调 Claude API 端到端 hello world**（验证部署链路）
  
  若 prototype 通过，进 Stage 4 SPEC；若发现致命问题（如 LLM 加工质量糟糕到必须改架构、CF Pages Functions 跑不动 Claude API），回 Stage 2 重议。

- 若用户决定跳过 Stage 3（接受风险）→ 直接进 Stage 4 SPEC，将上述高危风险作为 SPEC `Risks` 节明示。

**等待用户决定**：
1. 进 Stage 3 prototype？还是直接 Stage 4 SPEC？
2. 这份 02-grill-me artifact 是否需要修改 / 补充 / 删减？
