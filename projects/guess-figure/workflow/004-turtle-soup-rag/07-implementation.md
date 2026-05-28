# Stage 7 - Implementation 实现

> 详细规范见 [workflow-spec](../../../../workflow-spec/specification.md#阶段-7--implementation-实现)
>
> 要点：按任务清单顺序；一次一个；commit 映射到 task；发现 SPEC 缺口立即回 Stage 4，不静默偏离。
>
> v1.2 强制约定：进入 Stage 8 前必须调用 `verification-before-completion` skill 核对每条 AC 的 AI 验证证据。

---

## 进度

- [x] T1 - Cloudflare 资源与绑定契约 - commit: `df2d459` + `5988d12`。代码配置完成；本轮已验证 `wrangler whoami`、Vectorize/R2/D1 远端资源和 D1 manifest 表可访问。AC1 仍保留 Dashboard/manual：Vectorize 1024 维与 cosine metric 需人工取证。
- [x] T2 - 本地语料构建与 chunk 校验 - commit: `642dc73` + `5bed5e8`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T3 - Cloudflare 入库链路 - commit: `c283155` + `0fac610` + `76f360e` + `1c70e68` + 本轮修复待提交。真实 `--sample --cloud --mock-embedding` 已完成 R2 upload、Vectorize upsert、D1 manifest 三步；Windows 下默认 `pnpm.cmd exec wrangler`、D1 `--file` manifest 与 UTF-8 输出捕获已修复。
- [x] T4 - RAG 问题校验与缓存核心 - commit: `1963aca` + `e8a4795`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T5 - RAG 检索、rerank 与三态裁判 - commit: `1598f8f` + `91da358` + `a214c10`。SPEC review PASS；code-quality re-review APPROVED；最终整体验收修复 Workers AI embedding 矩阵响应兼容。
- [x] T6 - 海龟汤问答 API - commit: `e385921` + `d4e19b8`。SPEC review PASS；code-quality re-review APPROVED。
- [x] T7 - 答案提交与持久化状态 - commit: `b52508d` + `e21bc26` + `462e540` + `ad640c5`。SPEC re-review PASS；code-quality second re-review APPROVED；最终整体验收修复 completed session 提前拒绝，避免结束局消耗 RAG。
- [x] T8 - 极短隐晦汤面数据与校验 - commit: `d4064fb` + `0b4057f`。SPEC/code-quality re-review APPROVED。
- [x] T9 - 主游戏嵌入式 UI - commit: `eefd16a` + `e344533`。SPEC re-review PASS；code-quality re-review APPROVED。
- [x] T10 - 独立 `/turtle-soup` 玩法 UI - commit: `b378644` + `e344533`。SPEC re-review PASS；code-quality re-review APPROVED。
- [x] T11 - AC 验证脚本与 Stage 8 证据包 - commit: `dfd9930` + `4475201`。SPEC re-review PASS；code-quality re-review APPROVED。

## 偏离 SPEC 的发现

- 无。T11 只补 004 AC 验证脚本和 Stage 8 证据包，不修改业务行为。

## 当前阻塞

- AC1 仍需人工取证：自动化已确认 Cloudflare 账号、Vectorize/R2/D1 资源和 D1 manifest 表可访问；Vectorize 1024 维与 cosine metric 仍需 Dashboard/manual 记录。
- AC4 自动化仅覆盖 sample 的 `profile`、`wikipedia`、`wikisource` 三类 source type；完整 AC4 还需要全量二十四史 processed/failed 统计报告确认，当前不得标完整 PASS。
- Stage 8 是人工关卡，浏览器人工主路径尚未由用户实测；AC20 保持 MANUAL。

## 已运行的自动化检查

- `C:\Program Files\Git\bin\bash.exe scripts/verify_ac.sh`：exit code `1`；summary `PASS=17 FAIL=0 BLOCKED=1 MANUAL=2 SKIP=0`。AC2/AC3 已通过；AC1/AC20 为人工项，AC4 等待全量二十四史 processed/failed 报告。
- `python scripts/build_turtle_corpus.py --sample --cloud --mock-embedding --output <repo外临时目录>`：成功；cloud summary 包含 `r2_upload`、`vectorize_upsert`、`d1_manifest`。
- `pnpm test`：17 test files passed，150 tests passed。
- `pnpm run check`：0 errors，2 existing warnings：
  - `src/routes/play/+page.svelte:310` unused CSS selector `.result small`
  - `tsconfig.json:1` cannot find type definition file for `node`
- `pnpm run build`：pass；构建期间仍报告同一个既有 `.result small` unused CSS warning。
- `python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus scripts.tests.test_turtle_intro`：Ran 26 tests，OK。

## Stage 7 -> 8 verification-before-completion 核对

已使用 `verification-before-completion` skill。下表只记录 AI 验证通道；人工通道见 `08-qa.md`。

| AC | AI 验证命令 | 输出证据 | 状态 |
|---|---|---|---|
| AC1 | `pnpm exec wrangler whoami`; `pnpm exec wrangler vectorize list`; `pnpm exec wrangler r2 bucket list`; `pnpm exec wrangler d1 execute guess-figure-db --remote --command "SELECT name FROM sqlite_master WHERE name LIKE 'turtle_%';"` | `whoami` 成功；Vectorize index、R2 bucket、D1 manifest 表可见。脚本自动检查资源存在和 D1 表，Vectorize 1024/cosine 仍需 Dashboard/manual 取证。 | MANUAL |
| AC2 | `python scripts/build_turtle_corpus.py --sample --mock-embedding --output <repo外临时目录>`；`python scripts/build_turtle_corpus.py --sample --cloud --mock-embedding --output <repo外临时目录>` | 本地 dry-run 生成 `corpus_version`、`index_version`、`build-report.json` 和 `chunks.jsonl`；真实小样本云写入完成 R2 object upload、Vectorize upsert、D1 manifest，最终 build report 包含 cloud summary。 | PASS |
| AC3 | `git ls-files | rg '(^|/)(raw|normalized|chunks|wikisource|r2-cache).*\.(jsonl|txt|md)$|(^|/)corpus/|r2-cache'` | `scripts/verify_ac.sh` 报 `git 未跟踪全量原始/清洗语料、chunk JSONL 或 R2 cache`。 | PASS |
| AC4 | `python scripts/build_turtle_corpus.py --sample --mock-embedding --output <repo外临时目录>` 后检查 `build-report.json` | 自动化仅覆盖 sample source type coverage：`profile`、`wikipedia`、`wikisource` 三类来源；完整 AC4 待全量二十四史 processed/failed 统计报告确认。 | BLOCKED |
| AC5 | `python -m unittest scripts.tests.test_turtle_corpus` | Python corpus 测试覆盖 chunk 长度、overlap、metadata <10KiB 与来源追溯；相关总 Python suite 24 passed。 | PASS |
| AC6 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | RAG 单测覆盖 query expansion、目标人物姓名/aliases 注入与跨人物污染约束。 | PASS |
| AC7 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts` | RAG/API 单测覆盖可见回答枚举只允许“是/否/无关”。 | PASS |
| AC8 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | 证据不足 fixture 返回“无关”，不猜成“否”。 | PASS |
| AC9 | `pnpm exec vitest run src/lib/server/turtle-question.test.ts src/routes/api/turtle/question/server.test.ts` | invalid 不扣次数、不进入 RAG/LLM。 | PASS |
| AC10 | `pnpm exec vitest run src/lib/server/turtle-cache.test.ts src/routes/api/turtle/question/server.test.ts` | 缓存 key 含 figure/question/index/prompt version；TTL 30 天；hit 不查 Vectorize/LLM。 | PASS |
| AC11 | `pnpm exec vitest run src/lib/game-state.svelte.test.ts` | 主游戏状态测试覆盖第 1-5 条不显示入口、第 6 条后显示入口。 | PASS |
| AC12 | `pnpm exec vitest run src/lib/game-state.svelte.test.ts src/routes/api/game/finish/server.test.ts` | 嵌入式海龟汤最多 5 问；用后 finish payload / 持久化为 0 分。 | PASS |
| AC13 | `pnpm exec vitest run src/lib/turtle-soup-state.test.ts`; `python -m unittest scripts.tests.test_turtle_intro` | 首屏 round 只下发 `turtle_intro`，不暴露人物答案材料；65 人 intro 校验通过。 | PASS |
| AC14 | `pnpm exec vitest run src/lib/turtle-soup-state.test.ts src/routes/api/turtle/answer/server.test.ts` | 独立模式 15 问、3 次答案机会；错答只扣答案次数，不扣提问次数。 | PASS |
| AC15 | `pnpm exec vitest run src/routes/api/turtle/answer/server.test.ts` | 答案 API 只判目标人物命中，不读取 RAG 证据或要求解释故事。 | PASS |
| AC16 | `pnpm exec vitest run src/lib/server/turtle-question.test.ts` | 直接猜姓名/别名类 yes/no 问题不被 invalid 拦截。 | PASS |
| AC17 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts` | Workers AI/Vectorize/预算失败走 degraded；不误记为“否”或错误答案。 | PASS |
| AC18 | `pnpm exec vitest run src/lib/server/turtle-rag.test.ts` | 关羽“后世尊为武圣”维基 fixture 回归为“是”。 | PASS |
| AC19 | `pnpm test`; `pnpm run check`; `pnpm run build`; `python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus scripts.tests.test_turtle_intro` | `pnpm test` 150 passed；`check` 0 errors/2 existing warnings；`build` pass；Python 26 passed。 | PASS |
| AC20 | `scripts/verify_ac.sh` 只生成人工路径提示；浏览器主路径需 Stage 8 真人实测 | 脚本标 `MANUAL`，指向 `08-qa.md`。 | MANUAL |

## 2026-05-28 全量史料入库进展

- 已把本地离线脚本所需 `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` 写入项目 `.env`；`.env` 不进入 git，Pages runtime 仍使用 `wrangler.toml` bindings。
- 覆盖取证批次：`C:\Users\61780\AppData\Local\Temp\turtle-full-cloud-day1-20260528-103626\build-report.json`。该批次使用 `--max-pages-per-book 1`，完成 R2 upload、Vectorize upsert、D1 manifest；写入 696 个 chunk / vector，覆盖 65 个 profile、65 个 wikipedia、59 个 wikisource source，16/25 部史书至少有 1 页 processed。该批次只用于 AC4 覆盖取证，不作为真正全量续跑 checkpoint。
- 真全量序列批次：`C:\Users\61780\AppData\Local\Temp\turtle-full-cloud-seq1b-20260528-110129\build-report.json`。该批次未限制每书页数，完成 R2 upload、Vectorize upsert、D1 manifest；处理 `史記/卷001` 到 `史記/卷034`，写入 348 个 chunk / vector，`budget.next_resume_after` 为 `史記/卷034`。
- 远端核对：`pnpm.cmd exec wrangler vectorize info guess-figure-turtle-rag` 显示 `dimensions=1024`、`vectorCount=1036`；`wrangler vectorize get-vectors` 可取到新增 `史記/卷002` 向量。D1 `turtle_corpus_versions` 显示 `source_count=220`、`chunk_count=1032`、`vector_count=1032`、`failed_source_count=0`，`turtle_build_reports` 最新成功时间为 `2026-05-28 03:09:40` UTC。
- 下一批真实全量续跑命令应从 `史記/卷034` 之后继续，且继续不要使用 `--max-pages-per-book`：

```powershell
$out = Join-Path $env:TEMP ("turtle-full-" + (Get-Date -Format yyyyMMdd-HHmmss))
python scripts/build_turtle_corpus.py --full-history --cloud --skip-local-sources --output $out --resume-after "史記/卷034" --daily-token-budget 600000 --daily-vector-limit 700 --embedding-batch-size 8 --discovery-sleep 1.5
```

- 最终 AC4 自动化验收应使用 `TURTLE_FULL_REPORTS` 传入覆盖批次和所有真实全量序列批次的 `build-report.json`，脚本会聚合 `source_counts` 与逐书 `history_book_stats`。

## Stage 8 入场摘要预备

T11 已把旧 002 AC 验证脚本替换为 004 专用脚本。影响：`scripts/verify_ac.sh` 现在验证 `workflow/004-turtle-soup-rag` 的 AC1-AC20，不再假装旧 002 AC 是当前任务。Stage 8 需要用户重点补齐 Cloudflare Dashboard 远端资源截图/记录、真实 R2/Vectorize/D1 入库证据，以及两条浏览器主路径实测。

T11 代码与证据包改动已提交；本轮修复待提交。Stage 8 人工关卡尚未由用户确认，且 AC1/AC4/AC20 仍需补齐 Dashboard、全量或人工浏览器证据。
