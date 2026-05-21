# Prototype B — SvelteKit + CF Pages + LLM 部署链路验证

> Stage 3 prototype，throwaway 代码。验证完写结论到 [`../../03-prototype.md`](../../03-prototype.md)。

## 目的

压力测试 [Stage 2 grill-me](../../02-grill-me.md) 高危风险 4：**SvelteKit + CF Pages + +server.ts 部署链路用户无经验**。验证：

1. SvelteKit 5 + `@sveltejs/adapter-cloudflare` 本地 dev 跑得通
2. `+server.ts` 作为 CF Pages Function 部署后能跑
3. 环境变量在 CF Pages 上正确注入（platform.env vs process.env）
4. 从 CF Pages Function 调云雾 LLM API 链路全通

## hello world 范围

固定目标人物 = **诸葛亮**（异称表写死在前端）。用户输入任意名字 → 前端 POST `/api/check-answer` → `+server.ts` 调 LLM 判断 → 返回 `{correct, reason}` → 前端展示。

这跟 V1 实际场景的差别仅在"题库怎么来"（V1 从 `figures.json` 读，prototype 写死），核心链路完全一致。

## 跑（4 步）

### Step 1: 本地 dev 验证

```bash
cd projects/guess-figure/workflow/001-guess-figure/prototype/B-deploy

cp .env.example .env
# 编辑 .env 填 YUNWU_API_KEY (其他 2 项已默认)

pnpm install
pnpm dev
```

浏览器打开 `http://localhost:5173`，输入"孔明"提交，应该看到 `✅ 算对`。
打开"诸葛"提交，应该看到 `❌ 不算（仅姓氏太宽泛）`。

**走通这一步说明**：本地 SvelteKit + LLM 调用链路 OK。

### Step 2: build 验证

```bash
pnpm build
```

成功输出 `.svelte-kit/cloudflare/` 目录。**走通这一步说明**：adapter-cloudflare 编译没问题。

### Step 3: 推 GitHub

vibe-coding-lab 整仓库（含此 prototype 目录）push 到 GitHub。如果还没建 GitHub repo：

```bash
# 在 vibe-coding-lab 根目录
gh repo create vibe-coding-lab --public --source=. --remote=origin
git push -u origin main
```

如果已建过：
```bash
git add .
git commit -m "stage-3: prototype A + B 落地"  # 详细 commit message 见外层指引
git push
```

### Step 4: CF Pages 创建 project + 配 env vars + 部署

去 [Cloudflare Pages dashboard](https://dash.cloudflare.com/?to=/:account/pages)：

1. **Create a project** → **Connect to Git** → 选 vibe-coding-lab repo
2. **Project name**：`guess-figure-proto`
3. **Production branch**：`main`
4. **Build settings**：
   - Framework preset：**SvelteKit**
   - Build command：`pnpm install && pnpm build`
   - Build output directory：`.svelte-kit/cloudflare`
   - **Root directory（关键！）**：`projects/guess-figure/workflow/001-guess-figure/prototype/B-deploy`
5. **Environment variables**（Settings → Environment variables → Production）：
   - `YUNWU_API_KEY` = 你的云雾 key
   - `YUNWU_BASE_URL` = `https://yunwu.ai/v1`
   - `LLM_MODEL` = `gemini-3.1-flash-lite`
6. Save and Deploy

部署成功后访问 `https://guess-figure-proto.pages.dev` 测同样的输入。

**走通这一步说明**：CF Pages + +server.ts + env vars + LLM 调用 端到端 OK。Prototype B 通过。

## 测试用例 checklist

线上跑通后，逐条测：

- [ ] `孔明` → ✅ 算对（异称表内 → LLM 命中）
- [ ] `卧龙` → ✅ 算对
- [ ] `武侯` → ✅ 算对
- [ ] `诸葛丞相` → ✅ 算对（异称表外但 LLM 应识别）
- [ ] `诸葛孔明` → ✅ 算对
- [ ] `诸葛` → ❌ 不算（仅姓氏，应判 NO）
- [ ] `亮` → ❌ 不算（仅名，信息不足）
- [ ] `诸葛梁` → ❌ 不算（错字不容忍）
- [ ] `曹操` → ❌ 不算（不同人物）
- [ ] `司马懿` → ❌ 不算

## 评判产出（告诉我）

跑完 4 步 + 测试用例，给个评判：
- ✅ **V1 部署链路可接受**（进 Stage 4 SPEC）
- ⚠️ **某些细节要调**（哪些维度问题）
- ❌ **必须改架构**（如 adapter-cloudflare 跑不通、env vars 不能注入、LLM 调用被拦）

## 常见坑（提前预警）

- **CF Pages Root directory 没设对** → build 找不到 package.json，404
- **pnpm 版本不对** → CF Pages 默认 pnpm 版本可能跟你本地不一致，必要时在 Pages Settings → Environment variables 加 `PNPM_VERSION=9.0.0` 之类
- **环境变量没生效** → 改完 env vars 需要重新 deploy 一次（CF Pages env vars 是 build-time 注入到 platform.env）
- **超时**：CF Pages Function 默认 30s timeout，gemini 4s 内返回完全够
- **本地 dev `platform` 是 undefined**：脚本已 fallback 到 `process.env`，本地从 .env 读
