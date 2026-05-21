# Prototype A — 内容生产 pipeline 5 人验证

> Stage 3 prototype，throwaway 代码。验证完写结论到 [`../../03-prototype.md`](../../03-prototype.md)。

## 目的

压力测试 [Stage 2 grill-me](../../02-grill-me.md) 决策 2/3/4/7b 的高危风险：
- 维基中文 + Wikidata 主源拉数据是否稳定
- **DeepSeek V3 通过云雾中转加工出 7 条线索的质量**（这是 V1 最大未知）
- 你的人工审核能否拦住所有错误

## 跑法

### 1. 填 `.env`

```bash
cp .env.example .env
# 用编辑器打开 .env，填入：
#   YUNWU_API_KEY=sk-xxx       (云雾给你的 key，从云雾控制台拷)
#   YUNWU_BASE_URL=https://... (云雾的 base_url，云雾控制台/文档可查)
#   LLM_MODEL=deepseek-chat    (DeepSeek V3 在云雾上的模型名，看云雾文档)
```

### 2. 装依赖

```bash
# 推荐用 venv 隔离
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 3. 跑脚本

```bash
python proto_generate.py
```

预期：5 个人物，每个 ~10 秒（维基 + Wikidata + LLM）= 总 ~1 分钟。

### 4. 查看输出

`proto-figures.json` 含 5 人 × 7 条线索。

## 审核 checklist（你来做）

对每个人物，逐条线索检查：

| 维度 | 检查点 |
|---|---|
| **事实准确性** | 年份、官职、籍贯、作品归属对吗？拿出百度百科/维基对比 |
| **难度 1 关键约束** | **不含人名**（本名/字/号）、**不含朝代**、**不含最著名作品名**。这是最关键的硬约束 |
| **难度梯度** | 1 → 7 是否合理递进（先模糊→后具体→近答案）？任何一条偏离序列吗？ |
| **难度 7 关键约束** | 可以提朝代/部分作品，但**不含本名** |
| **异称完整** | 字、号、谥号、庙号是否齐全（如诸葛亮应含 "孔明"/"卧龙"/"武侯"）？参考百度百科对比 |
| **文字质量** | 每条 30-60 字、单句、无错别字、第三人称（不应有"我是 XX"） |

## 评判产出（告诉我）

跑完审核，给个评判：
- ✅ **V1 可接受**（不必调架构，可以进 Stage 4 SPEC）
- ⚠️ **prompt 要调**（哪几个维度有系统性问题，可靠改 prompt 修——告诉我哪些维度）
- ❌ **必须改架构**（如人工审核拦不住、或某个源不可用，需回 Stage 2）

## 已知不完美（V1 prototype 范围之外）

- 不做爬虫合规检查（仅维基/Wikidata，本身合规）
- 不做 LLM 输出 JSON 校验失败重试（错就报错给你看）
- 不存 LLM 原始响应日志（V1 prototype 验证概念，不做生产审计）
- 不做百度百科补充爬虫（决策 3 说仅对"维基资料不足"才补；5 个测试人物维基资料都很厚，用不到）

## 验证完后

清理：`.env` 不要 commit（已加 `.gitignore`）；`proto-figures.json` 也不必 commit（同上）；脚本和 README 进 commit 作为 prototype artifact 留痕。

下一步进 Prototype B（SvelteKit + CF Pages + Function + LLM 调用 hello world 部署），见 `../B-deploy/`。
