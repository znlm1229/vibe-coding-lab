# Stage 7 ｜ Implementation 实现

按 [README.md](./README.md) 跳过 Stage 1-6 + 8-9,仅本阶段落实际工作。

## 具体动作

| # | 动作 | 输出文件 |
|---|---|---|
| 1 | 写 003 复盘博客 | `src/content/posts/guess-figure-003-clue-optimization.md`(新) |
| 2 | 更新 guess-figure 项目卡加 V3 section | `src/content/projects/guess-figure.md`(改) |
| 3 | 润色现有 3 篇博客(轻度) | `src/content/posts/*.md`(改) |
| 4 | 更新 README 任务台账 +003 行 | `projects/personal-website/README.md` |
| 5 | commit + push 触发 CF Pages auto deploy | git + lw-personal.pages.dev |

## 内容设计要点

### 1. 新博客(guess-figure-003-clue-optimization.md)

frontmatter 沿用 [002 那篇](../../src/content/posts/guess-figure-002-account-rate-limit.md) 同款 schema。

主题:**3 步 LLM pipeline 重构 + prompt 2 轮调优 + 内容质量阶跃 + 65/70 偏差诚实记录**

主体结构:
1. 这次做的 3 件事(pipeline / 题库 50→65 / quality_check 4 项升级)
2. Stage 3 多 model 对比(haiku vs gemini-pro thinking-fail vs deepseek-v3.2)
3. Stage 8 抓到的 hard case 死循环(50 旧 14 failed + 20 新 10 failed)
4. prompt 调优 2 轮(profile aliases ≤ 5 / judge d6/d7 整字放可疑)
5. Wikisource mapping 阿拉伯数字 fix(LLM 凭知识写但没 verify 的教训)
6. regression 兜底 v1+v2 混合 + 65/70 偏差 explicit accept
7. 关键数据 123 测全 pass / ¥2.61 / 95.4% / 0 commit 动游戏机制

### 2. guess-figure 项目卡 V3 section

现有 V2 末尾追加 V3 section,跟 V2 同款 schema + 表格风格。
frontmatter:`summary` update + `tech[]` 加 "deepseek-v3.2" + `pubDate` 2026-05-26。

### 3. 润色现有 3 篇博客

**原则**:轻度(修笔误 / 补链接 / 不改语气)。

**实施前先 AI propose 改动给 user,用户拍板再 apply**(避免 over-edit)。

### 4. README 任务台账

加 003 行:`| 003 | [003-v3-content-refresh] | ✅ 已完成 2026-05-26 | 内容维护 |`

## verification-before-completion 跳过说明

Stage 7→8 之间的 `verification-before-completion` skill(v1.2 强制)在本任务**简化执行**:
- 没有 formal AC list(本任务 跳过 Stage 4 SPEC)
- 验证方式 = 用户在 lw-personal.pages.dev 浏览器看到新内容
- 验证证据 = git push 成功 + CF Pages dashboard build 成功

## Done when

- 1 个新博客 .md + 1 个项目卡更新 + 3 篇旧博客润色 commit 到 main + CF Pages auto deploy
- 访问 https://lw-personal.pages.dev/posts/guess-figure-003-clue-optimization/ 看到新博客
- 访问 https://lw-personal.pages.dev/projects/guess-figure/ 看到 V3 section
- /posts/ 列表 4 篇 + /projects/ guess-figure 更新日期 2026-05-26
