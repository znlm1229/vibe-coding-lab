# Stage 5 ｜ Plan 计划

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-5--plan-计划)
> 标准模板见 [`plan-and-tasks.md`](../../../../workflow-spec/references/plan-and-tasks.md)

---

## Approach

围绕 **"用 astro-paper starter 跑通 + 替换内容 + CF Pages 部署"** 的低风险路径走。**不从零搭框架、不写组件库**。

从社区 starter `astro-paper` 二次开发：
1. 删掉 starter 自带 demo 内容
2. 按 SPEC 三类内容线接入 Astro Content Collections（blog / projects）
3. 写 about / projects 自定义页（starter 默认主要是 blog 优先）
4. 替换 favicon / OG image / 头像 / 个人信息
5. 接 CF Pages 自动部署

**关键决策**（与 Brainstorm 时考虑过的方案比较）：

| 决策 | 选择 | 不选其它的理由 |
|---|---|---|
| Starter | `astro-paper` | 自带主题切换 / SEO / RSS / tag 系统，省去 Stage 7 大量配置；Astro 官方 blog template 偏裸需自己补 |
| 内容结构 | Astro Content Collections | 类型安全的 frontmatter；与 starter 默契 |
| 样式抽象 | 仅 Tailwind utility，不抽组件库 | MVP 阶段不引入设计系统层，避免过早抽象 |
| 邮箱混淆 | `mailto:` + JS 运行时拼接（如 `mailto:` + base64 解码） | 简单足以挡常见爬虫；图片渲染又一份资源开销 |
| 头像 | dicebear 生成 → 下载 SVG 到 `public/avatar.svg` | 不在运行时调外链，缓解外链失效与隐私泄露 |

## Phases

按依赖关系排序。每个 phase 是可独立 commit 的边界，**但还不是 task 粒度**（拆 task 在 Stage 6）。

### P1. 项目骨架就位

- **交付**：本地 Astro 项目可 `pnpm dev` 跑起来，看到 starter 默认页
- **为什么排第一**：所有后续工作的前置；先确认环境/工具/starter 没问题

### P2. Content Schema 与目录约定

- **交付**：`src/content/config.ts` 定义 blog / projects 两个 collection 的 frontmatter schema；目录约定写进项目本地 README
- **为什么排第二**：先把内容契约定下，才能往里灌内容；后续不会因 schema 改动反复返工

### P3. About 页（最小可行）

- **交付**：`/about` 路由 + 页面，含李旺自我介绍 + 邮箱（混淆）+ GitHub 链接
- **为什么这里**：about 简单、纯内容、不依赖其它；先做完一块拿一块

### P4. Projects 列表 + 详情页

- **交付**：`/projects` 索引 + `/projects/<slug>` 详情；放 1 张真项目卡（vibe-coding-lab）+ 1 张 "More coming" 占位
- **为什么这里**：项目是站点权重最高的一等公民；其页面模板会启发 P5

### P5. Blog 列表 + 详情页 + 1 篇 hello 文

- **交付**：`/blog` 索引（时间倒序）+ `/blog/<slug>`；OQ3 主题首篇博客文（介绍本站搭建 + 九步工作流）
- **为什么这里**：博客结构与项目相似，复用 P4 经验；hello 文兼作项目卡内容补充

### P6. 首页改造

- **交付**：`/` 改为 hero（头像 + 一句定位）+ 精选项目 + 最近博客 + 联系入口
- **为什么排在 P3–P5 之后**：首页要聚合三类内容，前面都做好首页才能整合

### P7. 站点元数据 / 404 / SEO meta / favicon / OG image

- **交付**：自定义 404 页、`<head>` SEO meta（site title, description, OG image fallback）、favicon、替换 starter logo
- **为什么这里**：所有页面做好后统一收尾元数据；可与 P8 并行

### P8. CF Pages 部署接入

- **交付**：CF Pages 接 GitHub repo，自动 build & deploy，`znlm1229.pages.dev` 公网可访问
- **为什么排第八**：本地全跑通再上线，避免反复 debug 部署

### P9. 验收前 AI 自检

- **交付**：本地+线上跑 AC1–AC13 一遍，问题列表 + 已修复清单
- **为什么排最后**：进 Stage 8 Human QA 之前 AI 自查，让 QA 阶段聚焦"机器没法测的人感受"

## Dependencies

- **P1 阻塞所有**：环境不通跑不动后面
- **P2 阻塞 P3–P6**：schema 没定 content 无法添加
- **P4 与 P5 半并行**（结构相似可参考实现）：建议**串行（P4 先）**避免重复决策
- **P6 强依赖 P3–P5**：首页聚合产物
- **P7 弱依赖 P1–P6**：可与 P8 并行
- **P8 强依赖 P1–P7 全部完成**：要部署的是完整站
- **OQ1 / OQ2 已答 ✅**：不再阻塞 P3
- **OQ3 / OQ4 已答 ✅**：不再阻塞 P5 / P4

## Risks

| 风险 | 概率 | 缓解 |
|---|---|---|
| starter 改动比想象的复杂（如想改 hero 布局） | 中 | SPEC 已限制"MVP 不动 starter 视觉"；强烈分歧回 Stage 4 改 SPEC |
| Lighthouse 性能 < 90（AC11） | 低 | Astro 默认零 JS + 系统字体；不引图片字体 web font；常见原因是首屏图片大，用 WebP/AVIF + size 限制 |
| CF Pages build 失败（依赖锁、Node 版本） | 低 | `package.json` engines 锁 Node 20+；commit `pnpm-lock.yaml`；CF 设 NODE_VERSION env |
| 中文字体在 starter 默认 light 模式对比度低 | 低 | P7 时检查并微调 Tailwind config（修 a11y，不算"改 starter 视觉"） |
| dicebear 头像 URL 失效 / API 变 | 低 | 生成后下载 SVG 到 `public/avatar.svg`，运行时不调外链 |
| AI 一上头直接动 starter 太多 | 中 | Task 粒度细 + 每 task commit；超出 SPEC 立即回 Stage 4 |
| OQ3 hello 文写得太长拖慢上线 | 中 | Tasks 中限定 hello 文 ≤ 600 字 + ≤ 2 小时写作时间 |
| 时区 / 日期格式踩坑（pubDate） | 低 | 全站用 ISO 8601（`YYYY-MM-DD`），不写时分秒 |

## Test strategy

| 检查 | 谁做 | 何时 |
|---|---|---|
| `pnpm build` 通过 + `pnpm preview` 可访问 | AI 在 Stage 7 每个 task 完成时 | 持续 |
| `astro check` 类型检查通过 | AI 在 commit 前 | 持续 |
| Lighthouse 桌面四项 ≥ 90（AC11） | AI 在 P9 自检阶段 | 上线前 |
| 移动端 375px 视口检查（AC6） | AI 用 DevTools responsive mode | P6 完成 + P9 |
| Stage 9 AC1–AC13 逐条 | 用户（Stage 8 / 9） | 上线后 |
| 内容工作流验证（AC7 / AC8） | AI 用临时文件演示 + 用户 Stage 8 实跑一遍 | P5 完成 + Stage 8 |
| 邮箱不明文 view-source 检查（AC10） | AI 在 P3 / P6 完成时 + 用户 Stage 8 | 持续 |

## 与 SPEC 的可追溯映射

| SPEC 项 | Phase 覆盖 |
|---|---|
| Goal 1 公网访问 | P8 |
| Goal 2 三类内容 | P3 / P4 / P5 |
| Goal 3 首页结构 | P6 |
| Goal 4 MVP 内容齐 | P3 + P4 + P5 |
| Goal 5 暗黑模式 | P1（starter 自带） |
| Goal 6 移动端 | P9 检查 |
| Goal 7 内容工作流 | P2 + P5 |
| Goal 8 artifact 完整 | 本 task 整体 |
| AC1 / AC2 | P8 |
| AC3 | P6 |
| AC4 | P3-P5 |
| AC5 | P1 |
| AC6 | P9 |
| AC7 / AC8 | P2 + P5 |
| AC9 | P1 + P7 |
| AC10 | P3 + P6（邮箱混淆） |
| AC11 | P9 |
| AC12 | 本 task 整体 |
| AC13 | P1 + P8 |
