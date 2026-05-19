# Stage 7 ｜ Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> **要点**：按任务清单顺序；一次一个；commit 映射到 task；**发现 SPEC 缺口立即停下回 Stage 4**，不要静默偏离。

---

## 进度（与 [`06-tasks.md`](./06-tasks.md) 同步）

### P1 项目骨架

- [x] **T1 — 初始化 Astro 项目（astro-paper starter）** ｜ commit: 待填
  - Astro 6.3.3 + Tailwind 4 + TypeScript 6 + Pagefind 搜索 + sitemap 等
  - 起步用 `git clone satnaing/astro-paper` 拉取，选择性拷贝（保留我们的 README/CLAUDE/workflow）
  - `pnpm install` + `pnpm rebuild esbuild sharp`（postinstall 授权）后 `pnpm build` 成功，生成 45 页 + sitemap + pagefind 搜索索引
- [ ] **T2 — 删除 starter demo 内容 + 锁定 Node 版本**

### P2 Content Schema

- [ ] T3

### P3 About 页

- [ ] T4, T5

### P4 Projects

- [ ] T6, T7, T8, T9

### P5 Blog

- [ ] T10, T11

### P6 首页

- [ ] T12, T13

### P7 元数据

- [ ] T14, T15, T16

### P8 部署

- [ ] T17, T18

### P9 自检

- [ ] T19

## 偏离 SPEC 的发现

<!-- 实现中如发现 SPEC 错 / 不全，记录在此并触发 SPEC 修订（回 Stage 4） -->

- T1：`pnpm install` 时 esbuild / sharp 的 postinstall 默认被忽略（pnpm 11.x 安全策略变化），需要 `pnpm approve-builds` 显式授权。这不算 SPEC 偏离，是依赖工具行为；记下在 README 或 CF Pages build settings 中要保证此授权生效。

## 已运行的自动化检查

- [x] `pnpm install` 成功（包数 ~615）
- [x] `pnpm build` 成功（45 页生成，含 sitemap + pagefind）
- [ ] `pnpm dev` 启动验证（暂跳过，build 通过推断 dev 也能跑）
- [ ] `pnpm astro check` 类型检查（T3 后做）
- [ ] Lighthouse 桌面四项（T19 阶段）

## Stage 8 入场摘要预备

> 完成本阶段前先准备好给 Stage 8 的"质检就绪摘要"草稿：改了什么、入口在哪、自动化通过情况。

待 T19 完成后填写。
