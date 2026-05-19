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

- [ ] T14, T15, T16

### P8 部署

- [ ] T17, T18

### P9 自检

- [ ] T19

## 偏离 SPEC 的发现

<!-- 实现中如发现 SPEC 错 / 不全，记录在此并触发 SPEC 修订（回 Stage 4） -->

- **T1**：`pnpm install` 时 esbuild / sharp 的 postinstall 默认被忽略（pnpm 11.x 安全策略变化），需要 `pnpm approve-builds` 显式授权。不算 SPEC 偏离，是依赖工具行为；T17 CF Pages build settings 中需保证此授权生效（或把 build 命令改为 `corepack enable && pnpm install --no-frozen-lockfile` 类）。
- **T2**：发现 starter 默认用 `src/content/posts/` + `/posts` URL，SPEC 原写 `/blog`。已在 SPEC v1.0.1 patch 中对齐为 `posts`/`/posts`。
- **T9（待修）**：starter `src/components/Footer.astro` 含硬编码 socials（X、LinkedIn、`mailto:yourmail@gmail.com`），违反 AC10（HTML 不含明文邮箱）。**T14 / T16 阶段必须替换 footer**：至少移除/替换 mailto 那条；其它 socials 看用户最终保留情况。

## 已运行的自动化检查

- [x] `pnpm install` 成功（包数 ~615）
- [x] `pnpm build` 成功（45 页生成，含 sitemap + pagefind）
- [ ] `pnpm dev` 启动验证（暂跳过，build 通过推断 dev 也能跑）
- [ ] `pnpm astro check` 类型检查（T3 后做）
- [ ] Lighthouse 桌面四项（T19 阶段）

## Stage 8 入场摘要预备

> 完成本阶段前先准备好给 Stage 8 的"质检就绪摘要"草稿：改了什么、入口在哪、自动化通过情况。

待 T19 完成后填写。
