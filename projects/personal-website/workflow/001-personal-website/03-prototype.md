# Stage 3 ｜ Prototype 原型

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-3--prototype-原型)
>
> **要点**：解决最大不确定性；最小可运行；用完即弃；当无真正不确定性时直接跳过。

## 决定

- [x] **跳过本阶段** —— 理由见下
- [ ] 构建原型

## 跳过理由

Stage 2 grill-me 已经把站点形态、技术栈、托管、设计调性、内容工作流全部敲定，**没有遗留的真正不确定性**需要靠原型来证伪：

| 候选不确定性 | 为什么不需要原型 |
|---|---|
| astro-paper 默认外观是否够看？ | 看官方 [demo 站](https://astro-paper.pages.dev/) 即可校准；"用就用，不行换 starter"成本极低 |
| bento 项目卡片网格在 Astro 是否可行？ | 标准 CSS Grid + Tailwind，零悬念 |
| Content Collections 处理 Markdown 是否顺手？ | Astro 官方文档与社区案例已饱和，标准模式 |
| Cloudflare Pages 自动部署是否顺畅？ | 一键集成 GitHub repo，无可证伪 |
| 暗黑模式实现 | starter 自带 |
| 中文字体回退是否好看 | 系统字体栈成熟方案，多个站点已验证 |
| 邮箱混淆方案 | `mailto:` + JS 混淆或图片渲染，方案明确 |

**结论**：当前路径清晰，做原型只是更慢的实现。按 specification §3 "规则一 按任务规模伸缩" + Stage 3 末段「当没有任何东西真正不确定时，跳过这个阶段」跳过本阶段，artifact 即此说明。

## 对 SPEC 的影响

无 —— SPEC 直接从 Stage 2 grill 输出构建。
