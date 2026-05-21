# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。
>
> **v1.2 关键约定**：
> - **AC 必须分两栏 AI 验证 / 人工验证**（两边都 PASS 才算 PASS）
> - **OQ 必须标 type**：`technical`（客观）vs `taste`（主观，AI 推荐仅占位）
> - SPEC 修订需显式版本号 + 修订日志，不许静默漂移

---

# SPEC: guess-figure V1 — 公开上线的中国历史人物猜谜 Web 游戏

**版本**：v1.0
**输入起点**：[Stage 2 grill-me](./02-grill-me.md) 9 决策 + [Stage 3 prototype](./03-prototype.md) 实测修订

## Summary

guess-figure V1 是一个 **公开上线、无需注册、面向陌生人** 的中国历史人物猜谜 Web 游戏。玩家选模式（日常练习 / 每日一题）→ 系统按难度从难到易给出 5 条标准线索 + 可选 2 条求救线索 → 玩家自由输入答案 → LLM 模糊匹配判定（识别异称如"诸葛亮 = 孔明 = 卧龙"）→ 得分 + daily 模式可分享。

## Problem

中文互联网上缺少 **聚焦中国史 + 渐进信息 + 自由输入** 的智力解谜游戏：

- Wordle 类游戏覆盖词汇，没覆盖"历史人物 + 多维线索"这种独特玩法
- 现有中国史小游戏多为"选择题刷题"模式，沉浸感弱、智力游戏感弱
- 玩家想以轻量、有趣的方式回顾或学习中国史人物，缺乏好的入口

V1 上线证明：(a) 这种玩法对中文用户是否有粘性，(b) 内容生产 pipeline 能否可持续支撑题库扩展，(c) 是否值得做 V2（账号 / 排行榜 / 多主题包等）。

## Goals

V1 必须达成的可观察成果：

- 公开上线（CF Pages 子域名可访问），陌生人无注册可玩
- 题库 ≥ 50 个中国史人物，每人 7 条线索（5 标准 + 2 求救）+ 3-5 个异称
- 两种模式：**日常模式**（随机抽题、无限玩）+ **每日一题**（全球同题、24 小时新换、限 1 次/天）
- 玩家自由文本输入答案 + 系统判定对错（异称表精确匹配 + LLM fallback）
- 计分公式：标准范围内用 k 条线索猜中得 `(6-k) × 20` 分（100/80/60/40/20）；求救范围内猜中得 10 分；放弃 / 失败 0 分
- daily 模式玩家可点击分享按钮得到含 emoji 进度的文字（"猜历史人物 #51 ❓❓❓✅ 用了 3 条线索"），方便复制到微信 / 朋友圈
- 内容生产 pipeline 可重复运行：`python scripts/generate_figures.py --new-batch N` → 你审核 → `git commit + push` → CF Pages 自动 redeploy

## Non-goals

V1 **明确不做** 的事（防止范围蔓延，每条都在 [02-grill-me](./02-grill-me.md) 锁定）：

| ❌ 不做项 | 推迟到 |
|---|---|
| 账号系统 | V2 |
| 排行榜（任何形式） | V2，跟账号一起 |
| daily 历史回看（玩昨天/上周的题） | V2 |
| 题库管理后台（带界面的 admin） | V2 / 可能永不做 |
| 用户报错通道 / 反馈表单 | V2（先加 `mailto:` 也行） |
| 多语言 / 英文版 | 可能永不做 |
| 自定义域名 | 单独开品牌化任务（不属于 V1）|
| 用户提交人物 / UGC | 可能永不做 |
| 移动 App / PWA | V2 / V3 |
| 付费 / 订阅 | 不在视野 |
| 反作弊（账号/IP/fingerprint）| V1 仅 localStorage，软漏洞接受 |

## Behavior

### Inputs

**玩家端**：
- 文本输入：答案（自由输入，中文为主，可能含字 / 号 / 朝代前缀等）
- 按钮：「猜」「再来一条」「求救（用 6-7 条）」「放弃看答案」「分享（daily）」「再玩一局（日常）」

**系统端（运行时）**：
- 从 `src/lib/data/figures.json` 读题库（V1 ≥ 50 人）
- 调云雾 API（`https://yunwu.ai/v1/chat/completions`）做 LLM 模糊匹配（仅当异称表精确匹配失败时）

**系统端（生产时，离线）**：
- Python 脚本：维基中文 + Wikidata（主源）+ 百度百科（手动补盲）→ LLM 加工成 figure JSON → 人工审核 → 合并入 `figures.json`

### Outputs

**前端**：
- 首页双入口（日常 / daily）+ 状态显示（daily 是否已玩）
- 游戏页：逐条展示线索、输入框、计分显示、失败时人物名 + 维基链接、daily 完成时分享按钮
- daily 完成状态：localStorage key `daily_played_{YYYYMMDD}=true`

**后端**：
- `POST /api/check-answer`：`{input, target}` → `{correct: bool, reason: string}`
- `GET /api/daily`：→ `{figure_id, date}`（按 UTC 16:00 切换 = 北京 0:00）

### Key flows

**Flow 1：日常模式（无限玩）**
```
1. 玩家访问 / → 点"日常游戏"
2. 前端从 figures.json 随机抽 1 个未被本 session 抽过的人物
3. 展示线索 1（最难）
4. 玩家可：
   a. 输入答案 + 点猜 → POST /api/check-answer → 显示对/错
      - 对 → 显示分数（100/80/60/40/20 视用了几条线索）→ "再玩一局" / "去 daily"
      - 错 → 不消耗线索次数，可继续输入或要下一条
   b. 点"再来一条" → 展示线索 2、3、4、5（共 5 条标准）
5. 5 条标准用完没猜中 → 显示"再要 2 条线索（求救模式，最高 10 分）" + "放弃看答案"
6. 求救：展示线索 6 → 输入或要 7 → 猜中得 10 分；7 条全用没猜中 → 自动显示答案
7. 放弃 / 失败 → 显示人物名 + 一句话简介 + 维基链接 + "再玩一局"
```

**Flow 2：每日一题模式**
```
1. 玩家访问 / → 点"今日挑战"
2. 前端 GET /api/daily → 拿到 figure_id
3. 检查 localStorage daily_played_YYYYMMDD（用户本地时区）
   - 已玩过 → 显示"今日已完成：X 分" + 分享按钮 + 倒计时下次换题
   - 未玩过 → 进游戏页（同日常 Flow，但限制只能玩 1 次）
4. 完成（猜中 / 求救 / 放弃）→ 写 localStorage + 显示分数 + 显示分享按钮
5. 分享按钮 → 把分享文本复制到剪贴板（"猜历史人物 #51 ❓❓❓✅ 用了 3 条线索 https://<domain>"）
```

**Flow 3：内容增量生产（离线）**
```
1. 你/cron 跑 python scripts/generate_figures.py --new-batch 10
2. 脚本：选 10 个新人物名 → 爬维基 + Wikidata → LLM 加工成 7 条线索 + 异称 + 难度标 → 输出 figures-new.json
3. 你 review 这 10 人（VS Code 看 JSON，改错的事实）
4. python scripts/merge.py → 合并入 src/lib/data/figures.json
5. git commit -m "task-TX: 题库 +10 人物" + git push
6. CF Pages auto build + deploy ~30 秒 → 用户下次刷新看到新题
```

### Edge cases

| 情况 | 行为 |
|---|---|
| 玩家输入空字符串或仅空格 | 前端不调用 API，按钮 disabled |
| 玩家输入仅姓氏（"诸葛"）| LLM 判 NO（信息不足，规则明示）|
| 玩家输入仅名（"亮"）| LLM 判 NO（信息不足）|
| 玩家输入错别字（"诸葛梁"）| LLM 判 NO（不容忍错字）|
| 玩家输入完全无关名字（"曹操"）| LLM 判 NO（reason 说明 "曹操不是诸葛亮"）|
| daily 题库耗尽（第 51 天起）| 进入"经典回顾"模式，按入库顺序轮播（前端显示"今日：经典回顾 第 N 期"）— **OQ1**（已决） |
| LLM API 调用失败（HTTP 5xx / 超时）| 前端显示"判定失败，请重试" + **不消耗线索次数 + 不计分**|
| 玩家关闭浏览器中途退出 | 进度不持久化（V1 不存 server state）；daily 已写入 localStorage 仍生效 |
| 玩家用隐身窗口 / 多浏览器刷 daily | 接受（V1 仅 localStorage 防复玩，软漏洞明示）|
| 移动端中文 IME 输入未确认就按提交 | 必须监听 `compositionend` 事件，IME 未结束不触发提交 |

### Error handling

| 错误 | 系统行为 |
|---|---|
| LLM HTTP 5xx | 后端返回 502 + 错误文本前 200 字到前端；前端 toast 错误信息 + 不消耗线索 |
| LLM HTTP 4xx（如 401 / quota） | 后端返回 500 + 写后端日志；前端通用错误 |
| LLM 响应超时（> 10s）| 后端 abort + 返回 504；前端通用错误 |
| LLM 返回非 JSON / schema 不符 | 后端按 `{correct: false, reason: "判定异常"}` 兜底返回 |
| `figures.json` 解析失败 | 前端展示"题库加载失败"（V1 阶段题库进 bundle，理论不会发生）|
| `GET /api/daily` 失败 | 前端隐藏 daily 入口（fallback 仅日常模式）|

## Constraints

### 技术栈（已锁定，[Stage 3 prototype 实测验证](./03-prototype.md)）

| 层 | 选型 | 理由 |
|---|---|---|
| 前端框架 | **SvelteKit 5** + Svelte 5 runes（`$state` / `$derived`） | 用户决策（决策 9）|
| 部署适配器 | `@sveltejs/adapter-cloudflare` ^4.7 | CF Pages 官方 |
| 后端运行时 | CF Pages Functions（即 `+server.ts` 文件，跑 CF Workers）| 跟前端同仓库同部署，零额外运维 |
| LLM 提供商 | **gemini-3.1-flash-lite** via 云雾中转（`https://yunwu.ai/v1`）| Prototype A 实测 4 维领先（决策 9b + Stage 3）|
| 题库存储 | **JSON-in-git**（`src/lib/data/figures.json`）| 决策 9b，V1 无用户数据无需 DB |
| 内容生产语言 | Python 3.10+ | 维基/Wikidata API 库成熟，决策 3 |
| 构建工具 | Vite ^5.4 + pnpm 11 | SvelteKit 默认 |
| 部署 | Cloudflare Pages（git push 自动 build & deploy）| 跟 personal-website 一致 |

### 性能预算

| 指标 | 目标 |
|---|---|
| 运行时 LLM 模糊匹配延迟（p95） | < 3s |
| CF Pages Function 单次执行 | < 30s（CF 硬限制；远超我们需要） |
| 题库 JSON 文件大小 | ≤ 200 KB（V1 50 人约 60-80 KB） |
| 首屏 LCP（移动 3G） | < 3s |
| 95% 玩家输入命中异称表（无需调 LLM） | 异称表完整度 KPI |

### 合规

- 爬虫源：维基中文 / Wikidata（CC-BY-SA / CC0 协议）自动爬；百度百科手动补盲（人类访问合规）
- LLM API key 仅 CF Pages env vars 持有，不暴露给前端
- 不收集用户个人信息（无登录、无 Cookie 个人化、无第三方 analytics）
- daily 模式 localStorage 仅存 `daily_played_YYYYMMDD=true`，无个人数据

### 兼容性

| 类型 | 支持目标 |
|---|---|
| 桌面浏览器 | Chrome / Firefox / Safari / Edge 最新两版 |
| 移动浏览器 | iOS Safari 15+、Android Chrome 最新两版 |
| 中文输入法 | 需正确处理 IME `compositionstart` / `compositionend` 事件 |
| 屏幕宽度 | 320px - 2560px（响应式）|

### 依赖与代码组织

```
projects/guess-figure/
├── src/                            ← 仅 V1 实际代码 + 题库（待 Stage 7 建）
│   ├── lib/data/figures.json       ← 题库（50 人 × 7 线索 × 异称）
│   ├── routes/
│   │   ├── +page.svelte             ← 首页双入口
│   │   ├── play/+page.svelte        ← 日常游戏页
│   │   ├── daily/+page.svelte       ← daily 模式页
│   │   └── api/
│   │       ├── check-answer/+server.ts   ← LLM 模糊匹配代理
│   │       └── daily/+server.ts          ← 今日题路由（按 UTC 16:00）
│   ├── app.html / app.d.ts
│   └── ...
├── scripts/
│   ├── generate_figures.py         ← 增量生产（从 prototype/A-content 提升）
│   └── merge.py                    ← 合并 figures-new.json
├── tests/                          ← Stage 7 决定单元测试位置
├── package.json / svelte.config.js / vite.config.ts / tsconfig.json
└── workflow/                       ← 已有的 workflow artifact
```

## Open questions

> 12 个 OQ，标 type（v1.2）。OQ6 已在 Stage 3 决定，OQ4 / OQ5 / OQ1 在本 SPEC 决定，其余 OQ7-12 全部 taste 类需用户拍板。

| # | 问题 | 类型 | AI 推荐 | 决定 | 阻塞节点 |
|---|---|---|---|---|---|
| OQ1 | daily 第 51 天起怎么办（题库耗尽降级）？ | technical | 进入"经典回顾"模式，按入库顺序轮播旧题；UI 显示"今日：经典回顾 第 N 期"；同时第 40 天起脚本告警提醒补题 | ✅ **确认推荐** | Stage 7 实施前 |
| OQ2 | 50 人具体名单怎么定？ | technical | 朝代分布（先秦/汉/唐/宋/明清/近代 各 8-10）+ 类型分布（帝王/军政/文学/思想家/科技 各 8-12）+ 知名度分布（一线 30 + 二线 15 + 冷门 5）。LLM 列 100 候选 → 你筛 50 | (待用户) | Stage 7 实施前（不阻塞 Stage 5/6） |
| OQ3 | LLM 模糊匹配 prompt 完整版定稿？ | technical | 沿用 prototype B 的 prompt 已实测（含规则 6 条 + 边界用例），Stage 7 实施前补 30-50 用例测试集 finalize | ✅ **沿用 prototype B prompt** | Stage 7 实施前 |
| OQ4 | daily 题选择策略（按入库顺序 / 难度均衡 / 手动指定）？ | technical | 按入库顺序（最简），V2 加难度均衡算法 | ✅ **按入库顺序** | Stage 7 |
| OQ5 | 失败显示答案后人物简介长度？ | technical | 一句话 + 维基百科链接（V1 极简）；V2 可考虑小卡片 | ✅ **一句话 + 维基链接** | Stage 7 |
| OQ6 | LLM 模型选择？ | technical | gemini-3.1-flash-lite via 云雾 | ✅ **已定**（Stage 3）| — |
| OQ7 | pages.dev 子域名？ | taste ⚠️ | prototype 期：`guess-figure-proto.pages.dev`；V1 上线：`guess-figure.pages.dev` 或 `lw-figure.pages.dev`（沿用 personal-website 的 `lw-` 个人前缀） | (待用户) | Stage 7 部署前 |
| OQ8 | 项目品牌名（中文）？ | taste ⚠️ | "猜历史人物"（直白）/ "他是谁"（悬念）/ "古今谁人"（文艺）—— 三个占位草稿 | (待用户) | Stage 7 写首页文案时 |
| OQ9 | 主色 / 视觉风格？ | taste ⚠️ | 极简（白底黑字 + 一色强调，Wordle 风）/ 中国风（米色底 + 朱砂红 + 古风字体）/ 卡牌风（每条线索一张卡片）—— 三种占位草稿 | (待用户) | Stage 7 实现 UI 时 |
| OQ10 | 分享文案 + emoji 风格？ | taste ⚠️ | `猜历史人物 #51\n❓❓❓✅ 用了 3 条线索\nhttps://<domain>`（标准 ✅ / 求救 🆘 / 失败 ❌） | (待用户) | Stage 7 实现分享时 |
| OQ11 | 首页文案 / Hero？ | taste ⚠️ | "猜历史人物 — 5 条线索，你能猜出他是谁？" | (待用户) | Stage 7 |
| OQ12 | 移动端布局风格（垂直流 / 卡片栈 / 水平滑动）？ | taste ⚠️ | 垂直流（最自然，符合 Web 直觉）；卡片栈适合"线索一张张展示"的仪式感 | (待用户) | Stage 7 |

> **taste OQ 处理原则**：AI 推荐**仅占位**，用户应在 Stage 7 实施时自己改写以匹配本人偏好；Stage 9 验收时**不以 taste OQ 的 AI 占位作为衡量标准**。

## Acceptance criteria

> Stage 9 会对照本节逐条核对。每条必须二选一可判定，且**必须分 AI 验证 + 人工验证两栏**（v1.2）。两边都 PASS 才算 PASS。

| # | 验收标准 | AI 验证 | 人工验证 |
|---|---|---|---|
| **AC1** | 网站可在公网访问，首页显示双模式入口 | `curl https://<url>` → HTTP 200，HTML 含"日常""今日"或等效关键词 | 浏览器打开看到首页 + 看见两个明显入口按钮 |
| **AC2** | 题库 ≥ 50 个中国史人物，每人 schema 完整 | `jq 'length' src/lib/data/figures.json` ≥ 50；`jq` 校验每条含 `{name, aliases[3-5], clues[7]{text, difficulty 1-7}, source, wiki_url}` | （schema 自动校验通过即可，无需人工） |
| **AC3** | 日常模式随机抽题，连玩多局至少 2 个不同人物 | `grep` 路由源码含随机抽题逻辑（Math.random / shuffle） | 浏览器点"日常游戏"5 次，至少看到 2 个不同人物 |
| **AC4** | 线索从难到易逐条展示，玩家可随时输入答案 | `grep` 组件含 `$state` 控制线索逐条显示 | 浏览器看到线索一条条出现（点"再来一条"才展示下一条），输入框始终可用 |
| **AC5** | 异称表精确匹配命中（"孔明"=诸葛亮）| 单元测试覆盖（无需调 LLM） | 浏览器输入"孔明" / "卧龙" / "武侯" → 显示 ✅ 算对 |
| **AC6** | LLM 模糊匹配 fallback（"诸葛丞相"）| 后端日志含 LLM 调用 + 返回 YES；本地脚本调 `/api/check-answer` 验证 | 浏览器输入"诸葛丞相" → 显示 ✅ 算对 |
| **AC7** | 错字 / 仅姓氏 / 仅名 一律不容忍 | 单元测试 + 后端日志 | 浏览器输入"诸葛梁"/"诸葛"/"亮" → 全部显示 ❌ 不算 |
| **AC8** | 求救机制：5 条标准用完可要 2 条求救线索 | `grep` 组件含求救按钮逻辑 + 计分公式 | 浏览器看完 5 条 → 看到"再要 2 条线索"按钮 → 点击 → 出现线索 6 → 再点 → 出现线索 7 |
| **AC9** | 计分公式正确 | 单元测试覆盖 `(6-k)*20` / 求救 10 / 放弃 0 | 浏览器多次玩验证 1 条 100 / 2 条 80 / ... / 6 条 10 / 放弃 0 |
| **AC10** | 失败后显示人物名 + 维基链接 | `grep` 失败逻辑含 `wiki_url` 字段引用 | 浏览器猜错 / 用完 7 条 / 放弃 → 看到人物名 + 一句简介 + 可点击的维基链接（点击新窗口打开维基百科）|
| **AC11** | daily 模式：同一天访问拿同一题 | `curl /api/daily` 多次返回同 `figure_id` | 浏览器无痕窗口多 tab 看 daily，看到相同人物 |
| **AC12** | daily 限 1 次/天（localStorage 防复玩） | `grep` 含 `localStorage.setItem('daily_played_...')` | 浏览器玩 daily 后刷新 → 显示"今日已完成"+ 分数 + 分享按钮 + 倒计时 |
| **AC13** | daily 分享按钮 → 文本复制到剪贴板 | `grep` 含 `navigator.clipboard.writeText` + 文本模板 | 浏览器点分享 → 看到"已复制"提示 → 粘贴到记事本验证格式（"猜历史人物 #N ❓❓❓✅ 用了 X 条线索 URL"） |
| **AC14** | 移动端响应式布局 + 中文 IME 输入正常 | CSS `@media` query 存在 + `grep` 含 `compositionend` 事件处理 | 真机 iPhone Safari / Android Chrome：(a) 看到布局不爆，(b) 中文输入法输入"孔明"按确认不会丢字提交 |
| **AC15** | LLM API 失败优雅降级（不消耗线索 / 不计分）| 模拟 LLM 5xx → 后端返回 502 → 前端 toast | 临时改 env vars 让 LLM key 失效 → 浏览器提交答案 → 看到错误提示 + 线索数不减 + 分数不变 |

## 修订日志

| 版本 | 日期 | 触发 | 变更范围 |
|---|---|---|---|
| v1.0 | 待用户确认 | Stage 4 初版 | 完整 SPEC 落地 |

---

## 用户确认

- ⬜ ~~等待确认~~
- ☑ **已确认** — 确认时间：2026-05-21 ｜ 备注：4 个 already-decided technical OQ（OQ1/3/4/5）认可；6 个 taste OQ（OQ7-12）留到 Stage 7 实施时由用户改写

> 一旦确认，本 SPEC 即为契约。后续修改需显式版本号 + 重新触发用户确认（不允许静默漂移）。
> Stage 9 Acceptance 会逐条对照本 SPEC 的 15 条 AC 验收。
