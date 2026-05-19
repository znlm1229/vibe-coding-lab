# Stage 4 ｜ SPEC 规格 ★ 人工关卡

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-4--spec-规格人工关卡)
> 标准模板见 [`spec-template.md`](../../../../workflow-spec/references/spec-template.md)
>
> **要点**：写"做什么"不写"怎么做"；验收标准必须**可测试**；**用户未确认前不得进入 Stage 5**。

---

## Summary

李旺的个人网站。一个极简学院派的多页静态站，含 **about / 项目卡片 / 博客** 三个一等公民内容线，面向**中文技术圈的潜在雇主与同行**，部署在 **Cloudflare Pages**。同时作为 vibe-coding-lab 九步工作流的第一个实战项目，承担流程学习载体。

## Problem

**要解决的问题**：
- 学习 vibe coding 工作流需要一个端到端真实项目承载；只跑到文档层属于"流程空转"
- 李旺在网络上缺少统一的身份与项目展示入口
- 未来求职需要一个可分享的链接，承载自我介绍 + 项目 + 思考

**不做会怎样**：
- 工作流学习只能停在文档层（没有真正"做出来"的 SPEC + 实现 artifact 对照）
- 求职铺垫无可挂载的具体物，等到要找工作时再临时建站效率低、心态被动

**为什么现在做**：lab 第一个项目要选一个真实、不太大、能跑通九步的题，个人网站正好（难度适中、范围可缩、可分享）。

## Goals

> 可观察的最终结果。每条都是"做到 / 没做到"二元可判定。

1. 网站可通过 `https://znlm1229.pages.dev/` 公网访问，HTTP 200
2. 网站包含且仅包含以下三类一等公民内容：
   - **About 页**：李旺的自我介绍 + 联系方式
   - **Projects 页**：项目卡片网格 + 每张卡可跳详情页
   - **Blog 页**：文章索引（时间倒序）+ 每篇可跳详情页
3. 首页（`/`）含 hero 区（一句自我定位 + 头像）+ 精选 1–2 张项目卡 + 最近 1–2 篇博客摘要 + 联系入口
4. MVP 上线版本至少包含：1 张真项目卡（vibe-coding-lab）+ 1 张 "More coming" 占位卡 + 1 篇 hello/intro 博客 + 完整 about 页
5. 全站支持暗黑 / 浅色模式切换（系统跟随 + 手动）
6. 全站中文为主，移动端可读（375px 宽视口正常）
7. 新增博客 / 项目卡的工作流是：**在指定目录加一个 `.md` 文件 → git push → 5 分钟内自动上线**，无需改 UI 代码
8. 九步工作流的全部 artifact（01 ~ 09）完整提交到 `projects/personal-website/workflow/001-personal-website/`

## Non-goals

> 与 Goals 同等重要，防 SPEC 阶段范围爆炸。

### 永不或长期不做

- ❌ 英文版 / 双语
- ❌ 任何后端 / 数据库 / 登录 / 评论 / 表单 / 动态服务
- ❌ SSR / Edge Functions / API routes
- ❌ Newsletter 主动经营
- ❌ CMS 后台
- ❌ APP / PWA 离线版 / 桌面端
- ❌ 付费内容 / 会员 / 打赏
- ❌ ICP 备案 / 国内 CDN
- ❌ 多人协作 / 编辑权限
- ❌ SEO 关键词卷 / 流量站玩法
- ❌ 展示 saleforteai 等商业 / NDA 代码
- ❌ 复杂动画（视差、cursor 跟随、滚动入场）

### MVP 阶段不做（推到上线后或二期）

- 评论系统（Disqus / giscus 等）
- 网站统计（GA / Plausible / CF Analytics）
- 自定义视觉细节（品牌色 / 字体 / 间距微调，**MVP 仅用 starter 默认**）
- 真人头像专门拍摄
- LinkedIn / Twitter/X / 微信链接
- 自定义域名（先用 `pages.dev` 子域名）
- 项目卡截图 broken link CI 校验
- 项目"超过 18 月自动 archived"特性
- 中英文之间自动加空格（pangu.js）

### 隐私 / 安全不做

- ❌ 展示手机号
- ❌ 展示具体住址 / 街区（城市级如"上海"可显示）
- ❌ 展示微信号 / 身份证 / 工作单位法人信息

## Behavior

### Inputs

- **维护者**：通过 `git push` 编辑 `src/content/` 下的 `.md` 文件来增删内容
- **访客**：HTTP GET 各页面 URL，浏览器渲染

### Outputs

- Cloudflare Pages 部署的静态文件：HTML / CSS / 极少 JS / 图片
- Build artifact：`dist/` 目录全部静态资源

### Key flows

1. **访客首次访问**：访问 `/` → 看到 hero + 精选项目 + 最近博客 → 通过导航跳 about / projects / blog
2. **访客读项目**：从首页或 `/projects` 点卡片 → 跳 `/projects/<slug>` → 查看截图 / 技术栈 / 描述 / 外链 GitHub
3. **访客读博客**：从首页或 `/blog` 点文章 → 跳 `/blog/<slug>` → 阅读正文 + 标签
4. **维护者发新博客**：
   ```
   1. 在 src/content/blog/ 创建 my-post.md（frontmatter: title, pubDate, description, tags, draft）
   2. 本地 pnpm dev 预览检查
   3. git add → commit → push
   4. CF Pages 自动 build & deploy（约 1–3 分钟）
   5. 访问公网 URL 验证生效
   ```
5. **维护者发新项目卡**：同上，目录为 `src/content/projects/`，frontmatter 含 `title, slug, summary, tech, githubUrl, liveUrl, screenshot, status`

### Edge cases

- 项目卡截图加载失败 → 显示灰色 placeholder（不要 broken image icon）
- 博客 `draft: true` → 仅本地预览出现，生产 build 跳过
- 项目卡 `status: archived` → MVP 阶段简单灰显或不区分（二期再做归档分区）
- 访客关闭 JS → 全站仍可读（站点零 JS 默认）
- 访客 375px 移动端访问 → 布局自适应，不出现横向滚动，文字可读
- 访客点击邮箱链接 → 触发系统邮件客户端（mailto:）

### Error handling

- 404 → 自定义友好 404 页（含返回首页链接 + 一句友好提示）
- 内部链接失效 → 由 Astro build 报错（不要静默上线）

## Constraints

### 技术栈

- **静态站生成器**：Astro 4.x+（LTS）
- **样式**：Tailwind CSS（不引入 daisyUI / shadcn）
- **包管理**：pnpm
- **内容存储**：Markdown / MDX in `src/content/{blog,projects}/`（Astro Content Collections）
- **Starter**：`astro-paper` 或 Astro 官方 blog template 任选其一
- **不引入**：React / Vue / Svelte 等组件运行时（仅 Astro 原生组件）

### 托管 / 部署

- Cloudflare Pages（接 GitHub 仓库自动部署）
- 域名：MVP 用 `znlm1229.pages.dev`；正式域名推上线 1–2 月后再决定
- HTTPS 由 CF 自动签发

### 性能预算（MVP 不强求 100% 达成，但是 Stage 9 验收基线）

- 首页 First Contentful Paint < 1.5s（Lighthouse 桌面）
- 首页 Largest Contentful Paint < 2.5s
- JS 总体积 < 50KB gzipped（理想 0KB，因 Astro 默认零 JS）
- 首页图片总体积 < 200KB（用 WebP / AVIF）

### 安全 / 隐私

- 联系邮箱必须用 `mailto:` + JS 混淆 或 邮箱图片渲染，**不**明文写在 HTML
- 不收集任何访客数据
- 头像图片来源必须有可证明的合法授权（推荐：dicebear 程序生成 / Unsplash CC0 / 自摄；**禁止**搜索引擎扒图）

### 字体

- 中文：系统字体栈（`PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif`）
- 英文：Inter（starter 默认）或系统字体兜底
- 等宽：JetBrains Mono / Fira Code（用于代码 snippet）
- **不引入** web font CDN（首屏更快、零外链依赖）

### 浏览器兼容

- 最近 2 年主流浏览器（Chrome / Safari / Firefox / Edge）+ 微信内置浏览器最低
- 不针对 IE 做任何兼容

### 内容工作流

- 新增内容路径：`src/content/blog/*.md` 或 `src/content/projects/*.md` + git push
- 全程零后台、零脚本
- 草稿用 `draft: true` frontmatter，生产 build 跳过

## Open questions

> 全部已在 SPEC 确认时解决。✅ = 已定。

| # | 问题 | 决定 | 备注 |
|---|---|---|---|
| ✅ OQ1 | 联系邮箱 | **`617809914@qq.com`** | 用户偏好用现有 git config 邮箱。AC10 邮箱混淆要求仍生效（不在 HTML 明文写）。 |
| ✅ OQ2 | 网图头像方案 | **dicebear 程序生成几何头像** | 生成后下载 SVG 到 `public/avatar.svg`，不在运行时调外链（缓解外链失效风险） |
| ✅ OQ3 | 第一篇 hello/intro 博客主题 | **「介绍本站搭建过程 + 九步工作流」** | 一文双用 —— 既是博客内容又是 vibe-coding-lab 项目卡的延伸支撑 |
| ✅ OQ4 | vibe-coding-lab 项目卡详情大纲 | **聚焦「九步工作流如何应用到本站搭建」** | 与 OQ3 互为引用，详情页可直接 link 到博客文章 |

## Acceptance criteria

> Stage 9 会逐条核对。每条必须二选一可判定。

1. **AC1（部署可达）**：访问 `https://znlm1229.pages.dev/` 返回 HTTP 200，浏览器看到非空首页内容
2. **AC2（页面齐全）**：以下 URL 全部返回 200 且渲染正确：`/`、`/about`、`/projects`、`/blog`，至少 1 个 `/projects/<slug>`，至少 1 个 `/blog/<slug>`
3. **AC3（首页结构）**：首页 DOM 中可见以下区块：hero（含一句自我定位 + 头像）、精选项目区（≥ 1 张卡）、最近博客区（≥ 1 篇）、联系入口（包含邮箱链接）
4. **AC4（MVP 内容齐）**：站点至少含 1 张真项目卡（vibe-coding-lab）、1 张 "More coming" 占位卡、1 篇 hello/intro 博客、完整 about 页
5. **AC5（暗黑模式）**：在网站可见位置有暗黑 / 浅色切换控件；点击后整站颜色切换；刷新页面后偏好保持
6. **AC6（移动端）**：iPhone SE 视口（375×667）打开首页与 1 个博客详情页，不出现横向滚动条，文字可读（≥ 14px 等效）
7. **AC7（内容工作流）**：在本地新建一个 `src/content/blog/test-acceptance.md` 含合法 frontmatter，`pnpm dev` 能本地渲染；删除该文件不影响其它
8. **AC8（草稿隔离）**：把任意博客文章 frontmatter 改 `draft: true` 后，本地 `pnpm build && pnpm preview` 中该文章不出现；去掉后又出现
9. **AC9（中文与字体）**：所有可见页面中文字符正常渲染（无方块 / 缺字），中文字体回退到系统字体（不引入 web font 远程加载）
10. **AC10（隐私守则）**：HTML 源码 `view-source:` 中**不**含明文邮箱字符串 `xxx@xxx.xxx`；联系入口的邮箱通过 `mailto:` + JS 混淆 或 图片渲染
11. **AC11（性能基线）**：Lighthouse 桌面端首页 Performance ≥ 90、Accessibility ≥ 90、Best Practices ≥ 90、SEO ≥ 90
12. **AC12（工作流 artifact 完整）**：`projects/personal-website/workflow/001-personal-website/` 下 01 ~ 09 全部存在；跳过的阶段 artifact 中写明「已跳过 + 理由」
13. **AC13（构建可重复）**：在干净环境（仅 Node 20+ 与 pnpm）`pnpm install && pnpm build` 一次成功，不依赖未声明的全局工具

---

## 用户确认

- ✅ **已确认** — 确认时间：**2026-05-19** ｜ 备注：OQ1 用户指定 `617809914@qq.com`（覆盖 AI 建议的独立邮箱）；OQ2/3/4 采纳 AI 建议
- ⬜ ~~等待确认~~

> 本 SPEC 已为契约。后续 Plan / Tasks / Implementation 全部对照本文件；Stage 9 Acceptance 对照本节 13 条 AC 逐条核对。修改本 SPEC 需显式重新确认（不允许静默漂移）。
