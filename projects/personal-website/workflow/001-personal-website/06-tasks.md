# Stage 6 ｜ Tasks 任务 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-6--tasks-任务人工关卡)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)
>
> **要点**：每个任务**可独立完成**；标 Touches / Done when / Depends on；**用户未确认前不得进入 Stage 7**。

---

## 任务清单（共 19 个 task，按依赖排序）

### P1 项目骨架

- [ ] **T1 — 初始化 Astro 项目（astro-paper starter）**
  - Touches: `projects/personal-website/src/` 全部（新建）；`package.json`、`pnpm-lock.yaml`、`astro.config.mjs`、`tailwind.config.cjs`
  - Done when: `pnpm install` + `pnpm dev` 跑起来浏览器看到 astro-paper 默认 demo 站
  - Depends on: nothing

- [ ] **T2 — 删除 starter demo 内容 + 锁定 Node 版本**
  - Touches: `src/content/blog/*`（删 starter demo posts）、`package.json#engines.node`
  - Done when: `src/content/blog/` 为空（保留 `.gitkeep`）；`package.json` 含 `"engines": {"node": ">=20"}`
  - Depends on: T1

### P2 Content Schema 与目录约定

- [ ] **T3 — 定义 blog 与 projects 两个 Content Collection schema**
  - Touches: `src/content/config.ts`（新建 / 改）
  - Done when: `pnpm astro check` 通过；schema 含 blog（title / pubDate / description / tags / draft）和 projects（title / slug / summary / tech / githubUrl / liveUrl / screenshot / status）
  - Depends on: T2

### P3 About 页

- [ ] **T4 — 写 about 页 Markdown 内容**
  - Touches: `src/pages/about.md` 或 `src/pages/about.astro` + 对应 frontmatter
  - Done when: `/about` 路由可访问，内容含李旺自我介绍（≥ 100 字）+ GitHub 链接 + 联系入口槽位
  - Depends on: T3

- [ ] **T5 — 实现邮箱混淆组件 + 接入 about 页联系入口**
  - Touches: `src/components/EmailLink.astro`（新建）；`src/pages/about.*`
  - Done when: about 页有可点击邮箱链接（触发 mailto），`view-source` 中**不**含明文 `617809914@qq.com` 字符串（AC10）
  - Depends on: T4

### P4 Projects

- [ ] **T6 — 写 vibe-coding-lab 项目卡 markdown（OQ4 主题）**
  - Touches: `src/content/projects/vibe-coding-lab.md`（新建）
  - Done when: 文件含完整 frontmatter；内容聚焦"九步工作流如何应用到本站搭建"；≤ 800 字
  - Depends on: T3

- [ ] **T7 — 写 "More coming" 占位项目卡 markdown**
  - Touches: `src/content/projects/more-coming.md`（新建）
  - Done when: 文件含 frontmatter（`status: wip` 或 `placeholder: true`）；正文一句话说明"项目持续补充中"
  - Depends on: T3

- [ ] **T8 — 实现 /projects 索引页（卡片网格布局）**
  - Touches: `src/pages/projects/index.astro`（新建）
  - Done when: `/projects` 显示 T6 + T7 两张卡（2-3 列响应式 grid）；每张卡显示 title / summary / tech tags / 跳详情链接
  - Depends on: T6, T7

- [ ] **T9 — 实现 /projects/[slug] 动态详情页模板**
  - Touches: `src/pages/projects/[...slug].astro`（新建）
  - Done when: `/projects/vibe-coding-lab` 与 `/projects/more-coming` 都可访问，渲染 frontmatter + markdown 正文
  - Depends on: T6, T7

### P5 Blog

- [ ] **T10 — 写第一篇 hello 博客（OQ3 主题）**
  - Touches: `src/content/blog/hello-and-the-nine-stages.md`（新建）
  - Done when: 文件含完整 frontmatter（pubDate=2026-05-19、tags=[vibe-coding, workflow]）；正文 ≤ 600 字（限定避免拖慢上线）；介绍本站搭建过程 + 九步工作流
  - Depends on: T3

- [ ] **T11 — 验证 /blog 索引页（用 starter 默认）+ 验证 /blog/[slug] 详情页（用 starter 默认）**
  - Touches: 视 starter 默认情况而定；如默认够用则仅验证；不够用则微调 `src/pages/blog/index.astro` / `src/pages/blog/[slug].astro`
  - Done when: `/blog` 显示 T10 的文章；`/blog/hello-and-the-nine-stages` 可读
  - Depends on: T10

### P6 首页

- [ ] **T12 — 集成 dicebear 头像并下载到 public/**
  - Touches: `public/avatar.svg`（下载）
  - Done when: `public/avatar.svg` 存在且大小合理（< 20KB）；运行时不调外链
  - Depends on: nothing（可与 T1-T11 任何点并行，但 T13 依赖它）

- [ ] **T13 — 改造首页为聚合页（hero + 精选项目 + 最近博客 + 联系）**
  - Touches: `src/pages/index.astro`
  - Done when: `/` 显示 4 区块：hero（头像 + 一句定位 + 名字"李旺"）、精选项目区（取 1-2 张项目卡缩略）、最近博客区（取最近 1-2 篇博客摘要）、联系入口区（含混淆邮箱）
  - Depends on: T5, T8, T11, T12

### P7 元数据 / 404 / SEO / favicon

- [ ] **T14 — 替换 favicon 与 OG image**
  - Touches: `public/favicon.svg`（或 .ico）、`public/og-image.png`、`astro.config.mjs` 中 site 字段
  - Done when: 浏览器 tab 显示新 favicon；`/` 页面 `<head>` 含 OG meta 指向 `og-image.png`
  - Depends on: T12（OG image 可复用 / 衍生自 avatar）

- [ ] **T15 — 自定义 404 页**
  - Touches: `src/pages/404.astro`
  - Done when: 访问不存在的路由如 `/nonexistent` 显示自定义 404 页，含返回首页链接与一句友好提示
  - Depends on: T13

- [ ] **T16 — 站点级 SEO meta（title / description / keywords / robots）**
  - Touches: `src/consts.ts` 或 starter 中的 site config；可能 `src/layouts/Layout.astro`
  - Done when: `/` `/about` `/projects` `/blog` 每个页面 `<head>` 都有 unique title 与 description
  - Depends on: T13

### P8 CF Pages 部署

- [ ] **T17 — 接 Cloudflare Pages 仓库 + 配 build settings**
  - Touches: CF Dashboard 配置（项目外部）；可能 `wrangler.toml`（如不需要可跳）；README 加部署说明
  - Done when: CF Pages 中能看到 vibe-coding-lab 的子项目设置；build command = `pnpm build`，output = `dist`，Node version = 20
  - Depends on: T1-T16 已能本地 build 通过

- [ ] **T18 — 触发首次部署并验证 znlm1229.pages.dev 可访问**
  - Touches: 一次 git push 触发；浏览器访问验证
  - Done when: `https://znlm1229.pages.dev/` 在浏览器返回 200，看到完整首页（AC1）
  - Depends on: T17

### P9 自检

- [ ] **T19 — Stage 9 前 AI 自检：跑 AC1–AC13 一遍 + 修复**
  - Touches: 视发现而定；输出问题清单到 [`07-implementation.md`](./07-implementation.md) 的「Stage 8 入场摘要预备」节
  - Done when: AC1-AC13 中至少 11 条满足（AC11 性能、AC6 移动端、AC10 邮箱混淆 是关键）；剩余项有明确"已知不达 + 理由"说明
  - Depends on: T18

---

## 任务统计

- **总 task 数**：19
- **关键路径**：T1 → T2 → T3 → (T4, T6, T7, T10) → (T5, T8, T9, T11) → (T12) → T13 → T16 → T17 → T18 → T19
- **可并行点**：T12 头像可与 T1-T11 任何时间并行；T7 占位卡可与 T6 并行；T14-T16 元数据三件可并行
- **预估时间**：单 task 约 5–30 分钟 AI 操作；总实施约 4–8 小时（含调试），分 2 个晚上跑完合理

---

## 用户确认

- ✅ **已确认** — 确认时间：**2026-05-19** ｜ 备注：用户「按你的想法来」全部 19 个 task 照走
- ⬜ ~~等待确认~~

> 本清单已为 Stage 7 进度追踪单位。改范围请显式回到本阶段重新讨论，**不能在 Implementation 中静默增删 task**。
