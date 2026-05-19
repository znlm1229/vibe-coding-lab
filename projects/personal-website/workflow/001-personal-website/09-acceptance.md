# Stage 9 ｜ Acceptance 验收 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-9--acceptance-验收)
>
> **要点**：逐条对照 SPEC 的 Acceptance criteria；二选一判定；**只有用户能说"通过"**。

---

## 验收核对表

> 对照 [`04-spec.md`](./04-spec.md) 的 13 条 Acceptance criteria 逐条核对。AI 列证据，用户判通过/不通过。

| # | 验收标准（SPEC 原文摘要） | AI 评估 | 证据 |
|---|---|---|---|
| AC1 | 访问 `https://lw-personal.pages.dev/` 返回 HTTP 200，浏览器看到非空首页 | ✅ 满足 | `curl https://lw-personal.pages.dev/` → HTTP 200, 18.6KB（T18 commit [700e528](https://github.com/znlm1229/vibe-coding-lab/commit/700e528)） |
| AC2 | 6 类 URL 全部返回 200：`/`、`/about`、`/projects`、`/posts`、`/projects/<slug>`、`/posts/<slug>` | ✅ 满足 | 6 个 URL `curl` 输出全 HTTP 200 |
| AC3 | 首页 DOM 含 hero / 精选项目 / 最近博客 / 联系入口（含邮箱链接）4 个区块 | ✅ 满足 | grep `id="hero/featured-projects/recent-posts/contact"` 在 `dist/index.html` 全在；用户实测 visual ✓ |
| AC4 | MVP 内容齐：1 真项目卡（vibe-coding-lab）+ 1 占位卡（More coming）+ 1 hello 博客 + 完整 about 页 | ✅ 满足 | files：`src/content/projects/vibe-coding-lab.md`、`more-coming.md`、`src/content/posts/hello-and-the-nine-stages.md`、`src/content/pages/about.mdx`；用户访问 ✓ |
| AC5 | 暗黑 / 浅色切换控件可见，点击切换，刷新后偏好保持 | ✅ 满足 | starter theme-btn + theme.ts（localStorage 持久化）；**用户实测 ✓** |
| AC6 | iPhone SE 视口（375×667）打开首页 + 1 博客详情，无横滚，文字 ≥ 14px 等效 | ✅ 满足 | **用户实测 DevTools 响应式 ✓ "全部通过"** |
| AC7 | 在 `src/content/posts/` 新建 `.md` 含合法 frontmatter，`pnpm dev` 能本地渲染；删除该文件不影响其它 | ✅ 满足 | T19 自检脚本：增 `test-acceptance.md` → build → 出 → 删 → build → 无 ✓ |
| AC8 | 博客 frontmatter 改 `draft: true` 后生产 build 中不出现；去掉后又出现 | ✅ 满足 | T19 自检脚本：改 draft / 撤 draft 切换验证 ✓ |
| AC9 | 中文字符正常渲染（无方块），中文字体回退到系统字体（不引 web font CDN） | ✅ 满足 | `<html lang="zh-CN">` ✓；`grep "fonts.googleapis\|cdn"` 在 dist 全 HTML = 0 ✓ |
| AC10 | HTML 源码不含明文邮箱 `xxx@xxx.xxx`；邮箱通过 `mailto:` + JS 混淆 | ✅ 满足 | site-wide grep `617809914@qq.com` 在 dist + 生产 HTML 都 = 0 ✓；EmailLink 客户端 atob 解码（Stage 8 修过一次 bug：commit [91fa174](https://github.com/znlm1229/vibe-coding-lab/commit/91fa174)）✓ |
| AC11 | Lighthouse 桌面端首页 4 项（Performance / Accessibility / Best Practices / SEO）≥ 90 | ✅ 满足 | **用户实测 Lighthouse ✓ "全部通过"**（具体分数用户未发，按用户判定为通过） |
| AC12 | `projects/personal-website/workflow/001-personal-website/` 下 01–09 完整；跳过的阶段写明「已跳过 + 理由」 | ✅ 满足 | 9 个文件全在；03-prototype.md 写「已跳过 + 理由」段 ✓ |
| AC13 | 干净环境（Node 20+、pnpm）`pnpm install && pnpm build` 一次成功 | ✅ 满足 | `rm -rf node_modules && pnpm install --frozen-lockfile && pnpm build` 本地 + CF 都跑通；package.json 含 `engines.node` 与 `packageManager` ✓ |

**总分：13 / 13 ✅**

---

## 已知非阻塞遗留（不影响 AC，可下一任务消化）

> 来自 Stage 8 用户实测发现，确认非阻塞、不打回。

| # | 项 | 建议去向 |
|---|---|---|
| 1 | Header 导航缺 `Projects` 入口 | 002 — UX 补 nav |
| 2 | Footer 仍含部分 starter 模板剩余（Copyright 文案、社交图标的 alt 文本等） | 002 — footer 清理 |
| 3 | About / hello 博客文案是 AI 起草占位 | 用户随时直接编辑 markdown，不需要走流程 |
| 4 | `default-og.jpg` 仍是 starter 默认 | 003 — 品牌 OG 图 |
| 5 | Pagefind 中文搜索无 stemming（精度有限） | 长期跟踪，pagefind 升级时回看 |

## 未满足项的回退方向

无。所有 AC 满足，无需打回任何阶段。

---

## 最终验收

- ⬜ **用户验收通过** — 时间：______ ｜ 备注：______
- ⬜ **打回** — 回到：⬜ Stage 4 SPEC ｜ ⬜ Stage 5 Plan ｜ ⬜ Stage 6 Tasks ｜ ⬜ Stage 7 Implementation

> 通过后请在项目根的 [`../../README.md`](../../README.md) 「任务台账」里登记本任务完成状态。

## SPEC 与实施的偏差记录

> Stage 4 SPEC 在实施过程中打了 2 个 patch，均为命名层/URL层不影响行为的修订，已在 SPEC §修订日志 记录：

- **v1.0.1**（T2 期）：`src/content/blog/` → `src/content/posts/`；`/blog` → `/posts`（采纳 starter 默认避免大量改名 refactor）
- **v1.0.2**（T17 期）：AC1 URL `znlm1229.pages.dev` → `lw-personal.pages.dev`（CF Pages 子域名 = 项目名，用户选了 lw-personal）

无静默漂移；所有修订均显式记录、可追溯。
