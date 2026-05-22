# scripts/ — 内容生产 pipeline

> T3 生产版（从 prototype A throwaway 代码提升）。用于 V1 题库 50 人 + V2 增量加题。

## 文件

| 文件 | 用途 |
|---|---|
| `generate_figures.py` | 调维基中文 + Wikidata + 云雾 LLM，生成 figure JSON |
| `merge.py` | 合并新批次到 `src/lib/data/figures.json`，去重 + 排序 + schema 校验 |
| `requirements.txt` | Python 依赖（requests / wikipedia-api / python-dotenv）|
| `logs/` | 运行日志（gitignore，不进仓库）|

## 准备

```bash
cd projects/guess-figure  # 项目根

# 1. 装 Python 依赖（推荐 venv 隔离）
python -m venv venv
venv\Scripts\activate           # Windows
# source venv/bin/activate       # Linux/Mac

pip install -r scripts/requirements.txt

# 2. 配 .env（项目根的 .env，跟 SvelteKit dev 共用）
cp .env.example .env
# 编辑 .env，填 YUNWU_API_KEY 即可（其他 2 项有默认）
```

## 跑

### 生成 1-2 个人物（测试）

```bash
python scripts/generate_figures.py --names "诸葛亮,李白"
```

输出 `figures-new.json`（项目根，已 gitignore），含 2 个完整 figure。

### 批量生产（T5 用）

```bash
# 一批 10 人（每批生产 + 你审核 + merge）
python scripts/generate_figures.py --names "诸葛亮,李白,武则天,朱元璋,鲁迅,白居易,曹操,赵匡胤,王安石,文天祥" --output figures-batch1.json
```

每个 figure 跑完立刻增量保存（整体挂掉不丢已成功的）。

### 命令行参数

```
--names         必填，人物名逗号分隔
--output        输出 JSON 路径（默认 figures-new.json）
--max-retries   LLM 失败重试次数（默认 2，指数退避 2s/4s/8s）
--model         LLM 模型（默认从 .env 的 LLM_MODEL，回退 gemini-3.1-flash-lite）
```

### 合并到主题库

```bash
# 1. 先 dry-run 预览不写
python scripts/merge.py figures-new.json --dry-run

# 2. 看输出 OK 再真合并
python scripts/merge.py figures-new.json
```

合并行为：
- 按 `id` 去重（新批次中跟主库已有 id 相同的跳过）
- 合并后按 `id` 排序
- schema 校验不合规的 figure 会弹确认（y 才合并）
- 报告新增 / 重复跳过 / 不合规列表

### Commit 规范

按 [workflow-spec v1.2 commit 前缀规范](../../../workflow-spec/references/plan-and-tasks.md#commit-conventions-v12):

```bash
# T5 每批 10 人
git add src/lib/data/figures.json
git commit -m "task-T5.1: 题库 +10 人物（先秦+汉）"

# 修题库错误（Stage 8 回路用）
git commit -m "fix(T5.2): 修李白生卒年错误（应为 701-762）"
```

## 工作流（T5 50 人生产推荐节奏）

> 边跑边审核，5 批 × 10 人推荐：

| 批次 | 朝代主题 | 候选人物（建议）|
|---|---|---|
| Batch 1 | 先秦+汉 | 孔子、孟子、老子、庄子、屈原、秦始皇、刘邦、汉武帝、司马迁、张衡 |
| Batch 2 | 三国+晋 | 曹操、刘备、诸葛亮、关羽、张飞、司马懿、王羲之、陶渊明、嵇康、谢安 |
| Batch 3 | 唐 | 李白、杜甫、白居易、唐太宗、武则天、玄奘、王维、韩愈、柳宗元、安禄山 |
| Batch 4 | 宋+元 | 苏轼、王安石、岳飞、文天祥、朱熹、辛弃疾、李清照、赵匡胤、成吉思汗、忽必烈 |
| Batch 5 | 明清+近代 | 朱元璋、郑和、戚继光、张居正、康熙、乾隆、林则徐、曾国藩、孙中山、鲁迅 |

每批跑完审核（quality_check.py - T4 完成后；当前 T3 阶段先人工 review）→ merge → commit → 下一批。

## 已知限制（V1 接受）

- 维基中文 / Wikidata 无条目的人物自动 skip（少数冷门人物）
- 单线程跑，10 人约 1 分钟（LLM 调用受 gemini-3.1-flash-lite ~4s 限制）
- 不做自动质量校验（T4 quality_check.py 任务负责）
- 不爬百度百科（V1 仅维基 + Wikidata；冷门人物维基资料不足时改造 T3 加百度补盲是 V2）

## 来源

提升自 [prototype A](../workflow/001-guess-figure/prototype/A-content/) 的 `proto_generate.py` + `batch_generate.py`（throwaway，已验证概念）。
