---
title: "给已上线的猜历史人物加账号 + 限流 + LLM 成本兜底 — 002 任务复盘"
description: "guess-figure V2：用九步工作流给已上线 Web 游戏补账号系统 + 双层限流 + LLM 成本兜底，22/22 AC 通过。复盘 5 个 production 部署的隐性陷阱：wrangler.toml 模式覆盖 dashboard vars、CF Workers fire-and-forget 被 kill、KV negative cache 60s、Git Bash UTF-8 编码损坏、CF Pages free plan rate limit 限制。"
pubDatetime: 2026-05-25T17:00:00+08:00
author: "李旺"
tags: ["vibe-coding", "workflow", "retrospective", "sveltekit", "cloudflare", "d1", "kv", "rate-limit", "llm-cost", "retrospective"]
featured: true
---

[guess-figure V1](/posts/guess-figure-retrospective/) 上线一周后我意识到：`/api/check-answer` **无 server 缓存、无每日预算上限**——脚本挂一晚（86400 秒 × ¥0.0005/call ≈ ¥45）即可击穿"个人小项目"的钱袋子。

V2（002 任务）就是为这个补保险。从 Stage 1 Brainstorm 到 Stage 9 用户验收**单 session 推完**，22/22 AC 通过，单测 66/66 pass。本文记录这次跑九步工作流抓到的 **5 个 production 部署的隐性陷阱**——都不在 SPEC 里，都不在事前知识里，全是 production 上踩出来的。

> 如果你不知道九步工作流是什么，先看 [Hello — 用九步工作流搭这个网站](/posts/hello-and-the-nine-stages/)。或者 [V1 复盘](/posts/guess-figure-retrospective/)。

## 这次做的：3 件事

1. **匿名 cookie 账号系统**：HMAC-SHA256 signed UUID + HttpOnly/Secure/SameSite=Lax + 滚动续期 365 天。"完全可选"——不强制注册，匿名也能玩、能存战绩。邮箱 / 跨设备同步推到下一个任务。
2. **双层限流**：CF dashboard Rate Limiting Rules（P）在边缘拦极端流量 + Workers KV 计数器（Q）按 IP/user 日窗口细粒度。**实际上 P 路径在 free plan 走不通**——成了 SPEC v1.0.1 patch 的重要 acknowledge。
3. **LLM 成本兜底三件套**：
   - **U** KV 缓存（key 含 `figure_id + aliases_hash + normalized_input`）—— 同输入第二次不调 LLM
   - **V** 全局日预算 8000 次（≈ ¥4.2/天上限）—— 超额进入降级模式
   - **X** 单 user 日上限 50 次 —— 单点滥用拦截

最终架构：CF D1（users + games 两表）+ 2 个 KV namespaces（限流计数器 + LLM 缓存）+ HMAC env secret + 6 个普通 env vars 阈值。

完整 [项目集 entry](/projects/guess-figure/) | [上线 URL](https://guess-figure.pages.dev) | [源码](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure)

## 工作流验证的赢点

| # | 赢点 | 关键证据 |
|---|---|---|
| 1 | **Stage 2 grill-me 12 轮拷问救命** | 在写代码前问"LLM 调用 prompt 里到底带不带 aliases？"——读现状代码后发现**带了** → 修正了我自己的推荐：cache key 必须含 `aliases_hash` 否则 aliases 改后 cache 给出过期结果 |
| 2 | **Stage 3 Prototype LLM 计费实测一锤定音** | 写脚本调云雾 100 次，单次 ¥0.000526（不是猜的）。V/X 阈值从"占位 5000/30"精确到"实测后 8000/50"。`--daily-budget-yuan 5` 命令参数让钱袋子上限可调 |
| 3 | **AC 双通道在产品行为上发挥** | 22 条 AC 每条都写 AI 验证路径 + 人工验证路径。降级 UX（degraded/network_error）的"不消耗线索"是核心人工验证项 — 浏览器 DevTools Offline 直接复现 |
| 4 | **fix(TX) 前缀让 bug 回路诚实记录** | 4 次 `fix(TX):` commits 区分于 23 次 `task-TX:` 首次实现 — git history 可清晰回溯每个 task 的"一次过 vs 多次迭代" |
| 5 | **/api/_debug 临时 endpoint 一次性定位 bindings 问题** | Stage 7 部署后 cache 永不命中，加了 30 行 debug endpoint 输出 platform.env keys + 类型 → 一次诊断出"binding 都在，但 fire-and-forget promise 被 kill" |
| 6 | **verification-before-completion skill 强制证据先于断言** | Stage 7→8 过渡时强制 skill 调用，把 22 个 AC 标 GREEN/YELLOW/RED。RED 项（AC5 free plan 限制）阻挡推进，必须 user 决策才能进 Stage 8 |
| 7 | **单 session 推完 + 用户战略干预** | 长 session 一路推 Stage 1-9，关键节点（SPEC / Tasks / Human QA / Acceptance / cost-sensitive 操作）停下让 user 拍板 |

## 5 个 production 部署的隐性陷阱

> 全是事前不知、读 doc 也找不到、需要在 production 实测才暴露的坑。给 v1.3 的失败模式输入。

### 1. wrangler.toml 模式覆盖 dashboard env vars

CF Pages 项目**一旦加 wrangler.toml**，dashboard 上 "Environment Variables" tab 配的 plain-text vars 被忽略，只有 secrets（encrypted）仍生效。

T17 部署后 `/api/check-answer` 直接报"缺 YUNWU_API_KEY 环境变量"。诊断半小时后看到 dashboard 上一行小字：

> *Environment variables for this project are being managed through wrangler.toml. Only Secrets (encrypted variables) can be managed via the Dashboard.*

修法：
- 非密变量（数字阈值 / endpoint URL / model 名）→ 写 wrangler.toml `[vars]` 段入 git
- 密钥（API key / HMAC secret）→ `wrangler pages secret put NAME --project-name guess-figure`

> 给 v1.3 的失败模式：**"加 wrangler.toml 到现有 Pages 项目时，旧 dashboard env vars 立即失效"**。

### 2. CF Workers fire-and-forget promise 在 response 后被 kill

最隐蔽也最痛的 bug。

代码大概这样写：

```ts
// LLM 调用成功后写 cache (fire-and-forget, 不阻塞响应)
cacheSet(cfEnv.GF_LLM_CACHE, key, llmResult).catch(() => {});
return json(llmResult);  // ← 立即返响应
```

直觉上：`cacheSet` 是个 Promise，event loop 应该自己跑完。**Wrong**——CF Workers 在 `return Response` 后**会 kill 所有未完成的 promise**，除非用 `ctx.waitUntil(promise)` 显式声明。

KV write 是网络往返，几乎一定在 response 前没完成 → 永远 kill → cache 永远不写入 → 下次请求永远 cache miss。

诊断过程：
1. dashboard 看 bindings 都在
2. 单测全过
3. production 实测 AC11 cache hit 永远 FAIL
4. 加 `/api/_debug` 临时 endpoint 输出 `platform.env` 所有 keys → 确认 `GF_LLM_CACHE: object(KV)` 注入了
5. 才想到 fire-and-forget pattern 的 CF Workers 特殊行为

修法：app.d.ts 加 `Platform.context.waitUntil` 类型 + 3 处 `platform?.context?.waitUntil(promise)` 包裹。

> 给 v1.3 的失败模式：**"CF Workers fire-and-forget Promise 在 response 后被 kill；必须 `ctx.waitUntil()` 才能让 KV write / counter INCR 完成"**。这条不在 CF docs 显眼位置。

### 3. CF KV cacheTtl 60s negative cache

waitUntil 修了之后还是 cache miss。why？

CF KV 的 `cacheTtl` 参数**最小 60 秒**（runtime 强制）。具体顺序：

1. 第一次请求：read `key` → 后端返 null → **runtime 缓存 "null" 60s**
2. 同 worker 写 `key = value` → 后端接受
3. 立即第二次请求（同边缘）：read `key` → **runtime cache 看到 "null"**（60s 内） → 返 null
4. 调 LLM → 再写一遍 → 仍 cache 不命中

[CF docs](https://developers.cloudflare.com/kv/api/read-key-value-pairs/) 实际有写但容易漏：
> The latest value of the key may not be available for **up to 60 seconds** after a `put`.

修法：测试脚本里 `sleep 65` 等 negative cache 过期。production 实际玩家不会"立即第二次"刷同一输入，这个延迟无感知。

> 给 v1.3 的失败模式：**"CF Workers KV 是 eventually consistent，cacheTtl 最小 60s；read-after-write 在 60s 内可能看到旧 null"**。AC 中"立即第二次命中"的测试方法对 KV 实现不适用。

### 4. Git Bash 字符编码损坏 UTF-8 中文字面值

写 production e2e 验证脚本时，bash 字符串字面量中的"诸葛亮"在 Windows Git Bash locale 下传给 curl 变成乱码字节，server 报"figure_id 不存在: �����"。

试了 `$'...'` ANSI-C quoting、`\uXXXX` JSON escape——都被 Anthropic Edit/Write 工具 API 自动解码成中文字面值，写入文件仍是 UTF-8 中文。

最后绕过：把 JSON payload 用 `node -e` 生成 base64 字符串硬编码到 bash 脚本里（纯 ASCII source），运行时 `base64 -d | curl --data-binary @-` 通过 stdin pipe 喂给 curl。**完全绕过 bash 字符串处理**。

```bash
# 纯 ASCII bash source
B64_ZHUGE_EXACT='eyJpbnB1dCI6IuivuOiRm+S6riIsImZpZ3VyZV9pZCI6IuivuOiRm+S6riJ9'
echo "$B64_ZHUGE_EXACT" | base64 -d | curl -s -X POST --data-binary @- ...
```

> 给 v1.3 的 best practice：**"涉及 CJK 字面值的 shell 脚本，用 base64 + stdin pipe 绕开 locale 问题，特别是 Windows + Git Bash 环境"**。

### 5. CF Pages free plan 不支持 dashboard Rate Limiting Rules

SPEC v1.0 设计了双层限流 P（dashboard）+ Q（Workers KV）。Stage 8 部署后 user 报告 70 次 POST 不触发 429，去 dashboard 找 Rate Limiting Rules 配置入口——**free plan 看不到这个功能**。

CF Rate Limiting Rules 现在仅 Workers Paid plan 及以上支持。SPEC v1.0 假设的 P 路径直接走不通。

修法是 **SPEC v1.0.1 命名层 patch**：
- AC5 验证路径转移到 Q（KV）按 IP 日上限触发
- C6 dashboard P 规则集标"free plan 不支持，待升级 / 自定义域名 + WAF 启用"
- server 行为不变（Q 一直 work），只是验证 trigger source 变了
- 用户 chat 明示"free plan 真不支持 可以容忍"接受

> 给 v1.3 的失败模式：**"SPEC 中假设外部基础设施提供的 feature（如 CF dashboard Rate Limiting / WAF）在 free plan 下不可用，规划时需要 verify plan capability before SPEC"**。

## 1 个意外的"反向证据"

Stage 7 末期 user 跑 verify_ac.sh 时报 `HTTP 429: 请求过于频繁 (rate-limit-ip)` —— 看起来是 bug，**实际是限流真生效的反向证据**。连续多次 e2e 测试累计 IP 请求达 `RATE_LIMIT_PER_IP_DAILY=200` 阈值后 server 阻断，正是 Q 计数器在做它应该做的事。

这个 user 的报错本身成了 AC5 的最佳人工验证证据 — 写进 09-acceptance.md 当作"Q 真触发 429"的实测记录。

> 给 v1.3 的 best practice：**"production e2e 测试可能因连续累计触发自己的限流；测试脚本需 SKIP_AC5=1 类 env flag 控制 + production 阈值需为测试留余地"**。

## Stage 9 验收后的小补丁

Stage 9 user 验收通过后两个微调：

1. **个人战绩 UI**：002 SPEC Non-goals 3 明示"排行榜 UI / 个人详情页留 003"，所以 002 没做 UI——但 user 测完发现"看不到自己历史记录"是体验缺失。`fix(T16):` 在首页加战绩区段（共 N 局 · 胜 M 局 · 近 5 局列表），15 分钟轻补，不动 SPEC / 后端 / 单测。
2. **RATE_LIMIT_PER_IP_DAILY 200 → 1000**：SPEC C3 默认 200 在共享 NAT 下误伤合法用户，user 决策调到 1000。**SPEC C3 已规约"env vars 可调"**，不算 patch。

## 整体感受

V2 是个**比 V1 更隐蔽的项目**——不增新功能（玩法体验对玩家透明），但加了 5 个新组件（D1 / 2 KV / cookie auth / 限流 / 缓存）+ 5 个新 endpoint 改动 + 6 个 env vars。**所有 bug 都在 production 部署后才暴露**，单测全过 + 类型检查零错 + AI grep AC 通过都拦不住。

总跨度 1 长 session（约 12-15 小时实际工时），但部署调试占了一半——5 个隐性陷阱每个都半小时到 2 小时不等。

提速来自：
- **v1.2 stage-skill 自动触发**——grill-me / verification-before-completion 该用就用
- **Stage 3 Prototype 一次性 LLM 计费实测**——V/X 阈值不再拍脑袋
- **第二次跑工作流的肌肉记忆**——不必再读 spec 思考下一步

代价：
- 单 session 长，token 消耗大
- 部署调试占用 50% 时间——CF docs 没显式列出来的 caveat 全靠 production 撞
- user 在长 session 中需要密集决策（4 个 ★ 人工关卡 + 多个 cost-sensitive 操作）

## 给 v1.3 的总反馈

**5 个失败模式**（来自这次复盘）：
1. wrangler.toml 模式覆盖 dashboard env vars
2. CF Workers fire-and-forget promise 在 response 后被 kill
3. CF KV cacheTtl 60s negative cache
4. Git Bash CJK 字面值 locale 损坏
5. SPEC 假设的基础设施 feature 在 free plan 下不可用

**3 个 best practice**：
1. 涉及 CJK 的 shell 脚本用 base64 + stdin pipe
2. SPEC 前确认外部基础设施 plan capability
3. production e2e 测试脚本需 SKIP env flag 控制 + 阈值留余地

这些都已 commit 在 [workflow/002-account-rate-limit/](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/002-account-rate-limit) 的 SPEC v1.0.1 修订日志、Plan 风险段、07-implementation 妥协标记里——下次跑工作流时这些都成知识库。

---

去玩玩 → [guess-figure.pages.dev](https://guess-figure.pages.dev)

完整 9 阶段 artifact 在 [仓库](https://github.com/znlm1229/vibe-coding-lab/tree/main/projects/guess-figure/workflow/002-account-rate-limit)（含 SPEC v1.0.1 修订日志 + 22 AC 满足核对表 + Stage 8 用户人工 check 清单）。
