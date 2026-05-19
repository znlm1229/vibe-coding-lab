# Stage 7 ｜ Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> **要点**：按任务清单顺序；一次一个；commit 映射到 task；**发现 SPEC 缺口立即停下回 Stage 4**，不要静默偏离。

---

## 进度（与 [`06-tasks.md`](./06-tasks.md) 同步）

### P1 项目骨架

- [x] **T1 — 初始化 Astro 项目（astro-paper starter）** ｜ commit: `45a0b45`
  - Astro 6.3.3 + Tailwind 4 + TypeScript 6 + Pagefind 搜索 + sitemap 等
  - 起步用 `git clone satnaing/astro-paper` 拉取，选择性拷贝（保留我们的 README/CLAUDE/workflow）
  - `pnpm install` + `pnpm rebuild esbuild sharp`（postinstall 授权）后 `pnpm build` 成功，生成 45 页 + sitemap + pagefind 搜索索引
- [x] **T2 — 删除 starter demo 内容 + 锁定 Node 版本** ｜ commit: 待填
  - 清空 `src/content/posts/*`（保留 `.gitkeep` 占位），重 build 通过（7 页）
  - `package.json` 重命名 `astro-paper-v6` → `personal-website`，加 description + private + 版本起步 0.1.0
  - `engines.node` starter 默认已是 `>=22.12.0`（强于 SPEC 的 ≥20，OK）
  - **发现 SPEC 偏差**：starter 默认用 `src/content/posts/` 集合 + `/posts` URL；SPEC 原写 `/blog`。打 SPEC v1.0.1 patch（命名层、不影响行为，已记在 SPEC 修订日志），见同次提交序列。

### P2 Content Schema

- [x] **T3 — 定义 blog / projects Content Collection schema** ｜ commit: 待填
  - starter 已有 `posts`（保留）+ `pages`（about 用）；本 task 新增 `projects` collection
  - projects schema 字段：title / summary / tech[] / githubUrl / liveUrl / screenshot / status (active|wip|archived) / pubDate / featured / order / draft
  - 创建 `src/content/projects/.gitkeep` 占位
  - `pnpm astro check` 通过：0 errors（2 hints 是 z.string().url() 在新 zod 中改为 z.url() 的废弃提示，不影响构建）

### P3 About 页

- [x] **T4 — 写 about 页 markdown 内容** ｜ commit: 待填（与 T5 合并提交）
  - 删除 starter `src/content/pages/about.md`（astro-paper 营销内容）
  - 新建 `src/content/pages/about.mdx`（用 mdx 而非 md 是为 T5 引入组件留口子）
  - 含李旺自我介绍 + 网站说明 + "在做什么" + 联系方式入口；TODO 注释标出可补充处
- [x] **T5 — 实现邮箱混淆组件 + 接入 about 页联系入口** ｜ commit: 待填（与 T4 合并提交）
  - 新建 `src/components/EmailLink.astro`：构建期 `Buffer.from(email).toString("base64")`，运行期 `atob()` 解码 → 设 `href="mailto:..."` + 可选替换显示文字
  - about.mdx 中 `import EmailLink` 并使用 `<EmailLink email="617809914@qq.com" />`
  - **AC10 验证通过**：`grep "617809914@qq.com" dist/` 返回空（无明文）；`data-email="NjE3ODA5OTE0QHFxLmNvbQ=="`（base64）写在 HTML 中

### P4 Projects

- [x] **T6 — vibe-coding-lab 项目卡 markdown** ｜ commit: 待填
  - `src/content/projects/vibe-coding-lab.md`：含 frontmatter（title / summary / tech / githubUrl / status=active / pubDate / featured=true / order=1）+ 正文（项目背景、九步流程做了什么、关键技术取舍、完整 artifact 链路）
  - 字数约 700（≤ SPEC 限的 800）；按 OQ4 聚焦"九步工作流如何应用到本站搭建"
- [x] **T7 — More coming 占位项目卡** ｜ commit: 待填
  - `src/content/projects/more-coming.md`：frontmatter（status=wip / order=99）+ 一句话说明"作品集陆续补充中"
- [x] **T8 — /projects 索引页（卡片网格）** ｜ commit: 待填
  - `src/pages/projects/index.astro`：取 `getCollection('projects')` 排序（featured 先 → order 升序 → title 字母兜底）；Tailwind grid（sm:cols-2 lg:cols-3）；卡片含 title / summary / tech tag / status badge
- [x] **T9 — /projects/[...slug] 详情页** ｜ commit: 待填
  - `src/pages/projects/[...slug].astro`：getStaticPaths 遍历 projects；渲染 frontmatter 元数据行（status / pubDate）+ tech tags + GitHub / liveUrl 链接 + Content 正文
  - 两个详情页 `/projects/vibe-coding-lab/` 与 `/projects/more-coming/` 均构建成功

### P5 Blog

- [x] **T10 — Hello 博客（OQ3 主题：本站搭建过程 + 九步工作流）** ｜ commit: 待填
  - `src/content/posts/hello-and-the-nine-stages.md`
  - frontmatter：pubDatetime=2026-05-19T10:00:00+08:00 / author=李旺 / tags=[vibe-coding, workflow, meta] / featured
  - 字数约 480（≤ SPEC 限 600）；含九步流程速览 + 各阶段做了什么 + 技术栈 + 完整 artifact 链接
- [x] **T11 — 验证 /posts 索引 + /posts/[slug] 详情（用 starter 默认）** ｜ commit: 待填（与 T10 合并）
  - starter 自带 `src/pages/posts/[...page].astro` + `src/pages/posts/[...slug]/index.astro` 默认工作良好
  - 验证：`/posts/index.html` 含 hello 文链接；`/posts/hello-and-the-nine-stages/index.html` 详情页生成 OK；pagefind 已索引

### P6 首页

- [x] **T12 — dicebear 头像下载到 public/** ｜ commit: 待填（与 T13 合并）
  - `curl https://api.dicebear.com/9.x/initials/svg?seed=李旺&backgroundColor=3b82f6&textColor=ffffff` → `public/avatar.svg`
  - 1109 字节（≤ SPEC 20KB 上限），CC0 1.0 授权（dicebear initials 标准协议）
  - 蓝底白字「李旺」initials；运行时不调外链
- [x] **T13 — 首页改造为聚合页（hero + 精选项目 + 最近博客 + 联系）** ｜ commit: 待填（与 T12 合并）
  - 全量替换 `src/pages/index.astro` starter "Mingalaba" 默认页
  - 4 个 `<section>`：hero（头像 + 名字 + 一句自我定位）/ featured-projects（取最多 2 张项目卡）/ recent-posts（最近 2 篇博客）/ contact（GitHub + EmailLink 混淆邮箱）
  - 验证：AC3 4 区块全在 dist/index.html；AC10 首页 grep `617809914@qq.com` 计数 = 0；avatar.svg 引用 OK

### P7 元数据

- [x] **T14 — 替换 favicon（OG image MVP 保留 starter default）** ｜ commit: 待填
  - `cp public/avatar.svg public/favicon.svg` 覆盖 starter 默认 favicon
  - 浏览器 tab 显示「李旺」蓝底白字 initials
  - **MVP 不替换 default-og.jpg**：satori 已开启 `dynamicOgImage`，每页自动生成 OG；首页/about 等 fallback 用 starter 的 default-og.jpg（acceptable for MVP，二期可自制品牌 OG）
- [x] **T15 — 自定义 404 页** ｜ commit: 待填
  - 重写 `src/pages/404.astro`：去掉 i18n 依赖，硬编码中文文案
  - 包含「404 大数字 + ¯\_(ツ)_/¯ + 友好提示 + 回首页链接」
  - 访问 `/nonexistent` 触发 404 时显示此页
- [x] **T16 — 站点级 SEO meta（title/desc/作者/语言/时区）+ 修 footer AC10 漏洞** ｜ commit: 待填
  - 全量替换 `astro-paper.config.ts`：title「李旺 · 个人网站」/ description / author=李旺 / lang=zh-CN / timezone=Asia/Shanghai / url=`znlm1229.pages.dev`
  - **socials 数组裁掉 mailto:yourmail@gmail.com 等 starter 占位**，只保留 `github` → 修复 T9 deviation log 中的 AC10 footer 漏洞
  - editPost 关闭（MVP 简化）
  - astro.config.ts i18n.locales = ["zh-CN"]，defaultLocale 同步（避免 getLocaleRelativeUrl 报 MissingLocaleError）
  - UI label（Posts / About / Tags 等）暂英文回退（useTranslations 内置兜底），post-MVP 可加 `src/i18n/lang/zh-CN.ts`
  - 验证：dist/index.html `<title>` = 「李旺 · 个人网站」（AC9）；site-wide HTML grep 邮箱字符串 = 0（AC10）；pagefind 提示 zh-CN 不支持 stemming 但搜索仍工作（可接受）

### P8 部署

- [x] **T17 — 接 Cloudflare Pages 仓库 + 配置 build** ｜ commit: 由用户在 CF dashboard 操作
  - 用户首次创建了 **Worker**（不是 Pages）→ wrangler 自动塞 `@astrojs/cloudflare` adapter → SSR build 失败（sharp 在 Workers runtime 不可用）
  - 修复：用户删 Worker，重建为 **Pages** 项目；项目名 `lw-personal` → 子域名 `lw-personal.pages.dev`
  - 项目配置：Build command `pnpm install && pnpm build`；Root dir `projects/personal-website`；Output `dist`；Env `NODE_VERSION=22`
  - 配套修复：删除 pnpm-workspace.yaml + 加 `packageManager: pnpm@10.11.1` 让 corepack 在 CF 用同版本（防 `packages field missing` 报错）
- [x] **T18 — 触发首次部署并验证** ｜ commit: 待填
  - 公网验证（2026-05-19）：
    - `curl https://lw-personal.pages.dev/` → **HTTP 200**, 18.6KB, 988ms
    - `<title>` = 「李旺 · 个人网站」
    - 6 个 key URL 全部 200：`/`、`/about/`、`/projects/`、`/posts/`、`/projects/vibe-coding-lab/`、`/posts/hello-and-the-nine-stages/`
    - 4 个首页 section id 全在生产 HTML 中（AC3）
    - 生产 HTML 中邮箱字符串匹配 = 0（AC10）

### P9 自检

- [x] **T19 — Stage 9 前 AI 自检** ｜ commit: 待填
  - **11/13 AC AI 已验证**：AC1 / AC2 / AC3 / AC4 / AC5（toggle 按钮 + theme.ts 存在）/ AC7 / AC8 / AC9 / AC10 / AC12 / AC13 ✓
  - **2/13 AC 需 Stage 8 人工在浏览器 DevTools 验证**：AC6（375px 移动端无横滚 / 文字可读）+ AC11（Lighthouse 桌面 4 项 ≥ 90）
  - 程序化验证脚本结果：
    - AC1 生产：HTTP 200, 18.6KB, 6 个 key URL 全 200
    - AC7 内容工作流：临时新增 `test-acceptance.md` → build → 出现 → 删除 → build → 不出现 ✓
    - AC8 draft 隔离：`draft: true` → 生产 build 不出现；去掉 draft → 出现 ✓
    - AC10 site-wide HTML grep 邮箱 = 0（本地 + 生产 HTML 都验证）✓
    - AC9 html lang=zh-CN + 0 个外部 web font CDN ✓
    - AC3 4 sections id 都在生产 HTML 中 ✓
  - 剩余 AC6 / AC11 转交 Stage 8 Human QA 阶段（人工在 Chrome DevTools 跑）

## 偏离 SPEC 的发现

<!-- 实现中如发现 SPEC 错 / 不全，记录在此并触发 SPEC 修订（回 Stage 4） -->

- **T1**：`pnpm install` 时 esbuild / sharp 的 postinstall 默认被忽略（pnpm 11.x 安全策略变化），需要 `pnpm approve-builds` 显式授权。不算 SPEC 偏离，是依赖工具行为；T17 CF Pages build settings 中需保证此授权生效（或把 build 命令改为 `corepack enable && pnpm install --no-frozen-lockfile` 类）。
- **T2**：发现 starter 默认用 `src/content/posts/` + `/posts` URL，SPEC 原写 `/blog`。已在 SPEC v1.0.1 patch 中对齐为 `posts`/`/posts`。
- **T9（已修 T16）**：starter `src/components/Footer.astro` 含硬编码 socials（X、LinkedIn、`mailto:yourmail@gmail.com`），违反 AC10。T16 通过 `astro-paper.config.ts.socials = [github only]` 修复。
- **T17（CF 部署）**：
  1. 用户项目名选 `lw-personal`（不是 SPEC 原假设 `znlm1229`），打 SPEC v1.0.2 patch 把 AC1 URL 改为 `lw-personal.pages.dev`。
  2. CF 首次 build 失败：`pnpm install --frozen-lockfile` 报 `packages field missing or empty`，因 `pnpm approve-builds` 在 pnpm 11 时自动创建的 `pnpm-workspace.yaml` 含 `allowBuilds:` 但缺 `packages:`。CF 使用 pnpm 10.11.1 拒绝。
  3. **修复**：删除 `pnpm-workspace.yaml`；package.json 加 `packageManager: "pnpm@10.11.1"`（pin 让 corepack 在本地 + CF 用同一版本）+ `pnpm.onlyBuiltDependencies: ["esbuild", "sharp"]`（pnpm 10 读这个字段；pnpm 11 不读但已弃用）。本地用 pnpm 10.11.1 复跑 `install --frozen-lockfile` + `build` 全绿，与 CF 等效。

## 已运行的自动化检查

- [x] `pnpm install` 成功（包数 ~615）
- [x] `pnpm build` 成功（每个 task 后均跑，全程绿）
- [x] `pnpm astro check` 类型检查通过（T3 后做，0 errors 2 hints）
- [ ] `pnpm dev` 交互启动验证（跳过，build 通过推断 dev 也能跑）
- [ ] Lighthouse 桌面四项（待 T18 上线后跑）

## Stage 8 入场摘要预备

> 给 Stage 8 Human QA 的"质检就绪摘要"草稿。

### 改了什么

完整端到端搭建 personal-website：基于 [astro-paper](https://github.com/satnaing/astro-paper) starter 二次开发，含 about / projects / blog 三个一等公民内容线 + 暗黑模式 + 邮箱混淆 + dicebear 头像 + 中文化配置。共 16 个 task commit + 1 个 SPEC v1.0.1 patch + 1 个 stage-6 确认 commit。

### 如何操作 / 入口

- 公网：**待 T17/T18 上线后填 URL**，预期 `https://znlm1229.pages.dev/`
- 本地：`cd projects/personal-website && pnpm install && pnpm dev` → 默认 http://localhost:4321
- 关键 URL：`/`、`/about`、`/projects`、`/posts`、`/projects/vibe-coding-lab`、`/posts/hello-and-the-nine-stages`、`/404`（试访 `/nonexistent`）

### 已通过的自动化检查

- AC2 / AC3 / AC4 / AC5 / AC7 / AC8 / AC9 / AC10 / AC12 / AC13 本地全部 ✓
- AC1 / AC6 / AC11 待上线后跑

### 建议人工重点测什么

1. **暗黑模式切换 + 持久化**：点击右上角 theme-btn，再刷新页面，看主题是否保留（AC5）
2. **移动端 375px 视图**：DevTools 切 iPhone SE 视口，看首页 / about / 项目详情 / 博客详情有无横滚 / 文字断裂（AC6）
3. **邮箱点击实际触发邮件客户端**：点击首页 / about 页的邮箱链接，看是否弹出默认邮件应用且收件人正确（AC10 配套）
4. **首页项目卡 + 博客卡 hover 反馈**：鼠标悬停时是否有边框 / 阴影变化
5. **菜单导航**：Header 菜单 Posts / Tags / About / Archives / Search 各点一遍，404 触发自定义页（AC2）
6. **首屏感觉**：第一眼是否清爽、字号 / 行高是否舒适、暗黑下对比度是否够（视觉品味，AI 看不准）
7. **Lighthouse 桌面 4 项**：DevTools → Lighthouse → Categories: Performance / Accessibility / Best Practices / SEO → Run Audit，确认全 ≥ 90（AC11）
8. **任何文案错别字 / 表达别扭**：about 页 / hello 文 / vibe-coding-lab 项目卡详情
