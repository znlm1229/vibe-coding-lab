# Stage 6 ｜ Tasks 任务 ★ 人工关卡

> 详细规范见 [workflow-spec](https://github.com/znlm1229/vibe-coding-lab/blob/main/workflow-spec/specification.md#阶段-6--tasks-任务人工关卡)
> 标准模板见 [`plan-and-tasks.md`](https://github.com/znlm1229/vibe-coding-lab/blob/main/workflow-spec/references/plan-and-tasks.md)
>
> **要点**：每个任务**可独立完成**；标 Touches / Done when / Depends on；**用户未确认前不得进入 Stage 7**。
>
> **v1.2 commit 前缀约定**：
> - `task-TX:` 新 task 首次实现
> - `stage-N:` 阶段产出 / 转换
> - `fix(TX):` 已完成 task 的 bug 修复（Stage 8 回路用）
> - `chore:` / `docs:` / `spec(vX.Y):` 其它治理
>
> **每个 task 的 Done when 必须可验证**（不能写"功能完成"这种主观断言，要写能跑出证据的条件）。

---

## 任务清单

- [ ] **T1 — <短名>**
  - Touches: <文件 / 模块>
  - Done when: <一两个可勾选条件>
  - Depends on: nothing

- [ ] **T2 — <短名>**
  - Touches:
  - Done when:
  - Depends on: T1

- [ ] **T3 — <短名>**
  - Touches:
  - Done when:
  - Depends on: T1

<!-- 任务过大（> 2 个 done-when 条件）拆成两个；不知道 Touches 说明 Plan 不够细，回 Stage 5 -->

---

## 用户确认

- ⬜ **等待确认**
- ⬜ **已确认** — 确认时间：______ ｜ 备注：______

> 一旦确认，本清单成为 Stage 7 的进度追踪单位。改范围请显式回到本阶段。
