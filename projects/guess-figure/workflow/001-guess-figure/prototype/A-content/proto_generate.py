#!/usr/bin/env python3
"""
Prototype A: 内容生产 pipeline 端到端 5 人验证

跑法：
  1. cp .env.example .env，填入云雾 API key + base_url
  2. pip install -r requirements.txt
  3. python proto_generate.py

输出：proto-figures.json (5 人 × 7 条线索) 由你人工审核
"""

import json
import os
import re
import time
from pathlib import Path

import requests
import wikipediaapi
from dotenv import load_dotenv

load_dotenv()

# ===== 配置 =====
TEST_FIGURES = [
    {"name": "诸葛亮"},
    # 临时只跑 1 人验证 pipeline 输出结构；跑通后取消下面注释跑全 5 人
    # {"name": "李白"},
    # {"name": "武则天"},
    # {"name": "朱元璋"},
    # {"name": "鲁迅"},
]

OUTPUT_PATH = Path(__file__).parent / "proto-figures.json"
USER_AGENT = "guess-figure-prototype/0.1 (vibe-coding-lab; ai-research)"

WIKIPEDIA = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT,
    language="zh",
    extract_format=wikipediaapi.ExtractFormat.WIKI,
)

LLM_API_KEY = os.environ["YUNWU_API_KEY"]
LLM_BASE_URL = os.environ.get("YUNWU_BASE_URL", "https://yunwu.ai/v1").rstrip("/")
# 兜底：如果 base_url 没带 /v1，自动补上（OpenAI-compatible 标准路径）
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")


def fetch_wikipedia_summary(name: str) -> str:
    """拉维基中文条目摘要（前 1000 字，给 reasoning model 留思考预算）。"""
    page = WIKIPEDIA.page(name)
    if not page.exists():
        return f"[维基中文无 '{name}' 条目]"
    return page.summary[:1000]


def search_wikidata_qid(name: str) -> str:
    """根据中文人名搜 Wikidata QID（取第一个匹配）。避免硬编码 QID 写错。"""
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "zh",
            "format": "json",
            "type": "item",
            "limit": 5,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("search", [])
    if not results:
        raise RuntimeError(f"Wikidata 搜不到 '{name}'")
    return results[0]["id"]


def fetch_wikidata_fields(qid: str) -> dict:
    """拉 Wikidata 结构化字段：标签、描述、别名、生卒年。"""
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "format": "json",
        "languages": "zh|en",
        "props": "labels|aliases|claims|descriptions",
    }
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    entity = r.json()["entities"][qid]

    claims = entity.get("claims", {})

    def extract_time(prop):
        try:
            return claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"]
        except (KeyError, IndexError, TypeError):
            return None

    return {
        "label_zh": entity.get("labels", {}).get("zh", {}).get("value", ""),
        "label_en": entity.get("labels", {}).get("en", {}).get("value", ""),
        "description_zh": entity.get("descriptions", {}).get("zh", {}).get("value", ""),
        "aliases_zh": [a["value"] for a in entity.get("aliases", {}).get("zh", [])],
        "birth": extract_time("P569"),
        "death": extract_time("P570"),
    }


PROMPT_TEMPLATE = """你是中国历史人物题库编辑。我给你 1 位历史人物的原始材料，请你输出严格 JSON 格式的题目数据。

输出 schema：
{{
  "name": "<本名（确认是这个人的本名，不是字号）>",
  "aliases": ["<异称1>", "<异称2>", "..."],
  "clues": [
    {{"text": "<难度 1: 最难，不能提人名/朝代/著名作品名>", "difficulty": 1}},
    {{"text": "<难度 2>", "difficulty": 2}},
    {{"text": "<难度 3>", "difficulty": 3}},
    {{"text": "<难度 4>", "difficulty": 4}},
    {{"text": "<难度 5: 标准范围内最易>", "difficulty": 5}},
    {{"text": "<难度 6: 求救线索，直接给关键事迹/著名作品>", "difficulty": 6}},
    {{"text": "<难度 7: 几乎暴露答案，可提朝代+作品名但不直接给本名>", "difficulty": 7}}
  ]
}}

规则：
1. aliases 必须真实历史记载：字、号、谥号、庙号、别号、绰号。不要编造。一般 3-5 个。
2. 每条 clue 30-60 字，单句陈述。
3. 难度 1-5 严格从难到易递进；难度 6-7 是"求救"用，已经接近暴露答案。
4. **难度 1-5 全段绝不出现 aliases 中任何一个异称**（本名/字/号/谥号/庙号/别号/绰号/姓氏单字）。一旦出现"卧龙"这种异称就直接暴露答案，等于规则崩盘。
5. **难度 1 额外约束**：不出现朝代名、不出现最著名作品名、不出现最标志性事件（如"三顾茅庐""三气周瑜""草船借箭"对诸葛亮）。要难到"专精历史的人也得想 3 秒"才合格。
6. 难度 6-7 求救线索可以出现：朝代、部分作品名（如"代表作《出师表》"）、标志性事件，但**仍不出现本名**。
7. 用第三人称描述（"他"/"她"），不出现"我是 XX"等第一人称。
8. 严格输出 JSON，前后无 markdown 代码块标记，无其他说明文字。

自检清单（生成前过一遍）：
- [ ] 把 aliases 里所有字眼都标记下来，确认 clues[0..4].text 都不含任何一个
- [ ] 难度 1 是不是"普通爱好者"也得犹豫几秒？太标志性的典故要藏到难度 4+

原始材料：
{material}

人物中文名：{name}
"""


def generate_figure(name: str, material: str) -> dict:
    """调 LLM 把原始材料加工成 figure JSON（requests 直接 POST，避免 SDK 吞错）。"""
    prompt = PROMPT_TEMPLATE.format(material=material, name=name)
    url = f"{LLM_BASE_URL}/chat/completions"

    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 8000,  # reasoning model 思考链 6000+ token，留 2000 给 output
        },
        timeout=300,  # reasoning model 单次推理可能 2-5 分钟
    )

    if r.status_code != 200:
        raise RuntimeError(
            f"HTTP {r.status_code} from {url}\n"
            f"  响应前 500 字: {r.text[:500]}\n"
            f"  排查: (1) base_url 是否对（应类似 https://yunwu.ai/v1）"
            f" (2) LLM_MODEL='{LLM_MODEL}' 云雾是否支持（控制台查模型列表）"
            f" (3) API key 是否有效"
        )

    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(
            f"响应非 JSON: {e}\n"
            f"  raw 前 500 字: {r.text[:500]}"
        )

    if "choices" not in data:
        raise RuntimeError(
            f"响应缺 choices 字段（非 OpenAI 兼容格式）\n"
            f"  完整响应: {json.dumps(data, ensure_ascii=False)[:500]}"
        )

    msg = data["choices"][0]["message"]
    raw = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    finish_reason = data["choices"][0].get("finish_reason", "?")

    if not raw:
        raise RuntimeError(
            f"LLM 返回 content 为空 (reasoning model 卡在思考阶段)\n"
            f"  finish_reason: {finish_reason}  (length=token 跑完, stop=正常结束)\n"
            f"  reasoning_content 长度: {len(reasoning)} 字 (前 300 字: {reasoning[:300]})\n"
            f"  建议: (1) max_tokens 已是 4000，若 finish_reason=length 还需加大\n"
            f"        (2) deepseek-v4-pro 是 reasoning model，考虑换非 reasoning 模型\n"
            f"            (云雾控制台'模型列表'看完整可用 LLM，gpt-4o-mini / claude-haiku 类标准 chat 模型更稳)"
        )

    text = raw.strip()

    # 容错 1: 剥 reasoning model 的 <think>...</think> 标签（DeepSeek R1 等）
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 容错 2: 剥 markdown 代码块包装 ```json ... ```
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

    # 容错 3: 如果仍不以 { 起始，用正则抠第一个 {...} 块（容忍 LLM 在 JSON 前后乱说话）
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            text = match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"LLM 返回的内容无法解析为 JSON: {e}\n"
            f"  原始 content (前 1200 字): {raw[:1200]}\n"
            f"  提取后的 text (前 600 字): {text[:600]}"
        )


def main():
    print(f"配置: base_url={LLM_BASE_URL}, model={LLM_MODEL}")
    figures = []
    for idx, fig in enumerate(TEST_FIGURES, 1):
        name = fig["name"]
        print(f"\n[{idx}/{len(TEST_FIGURES)}] 处理：{name}")

        try:
            print("  → Wikidata 搜 QID...", end=" ", flush=True)
            qid = search_wikidata_qid(name)
            print(f"OK ({qid})")
            time.sleep(1)

            print("  → 维基中文...", end=" ", flush=True)
            wiki_summary = fetch_wikipedia_summary(name)
            print(f"OK ({len(wiki_summary)} 字)")
            time.sleep(1)

            print("  → Wikidata 字段...", end=" ", flush=True)
            wd_fields = fetch_wikidata_fields(qid)
            print("OK")
            time.sleep(1)

            material = f"""维基中文摘要：
{wiki_summary}

Wikidata 字段：
- 中文标签: {wd_fields["label_zh"]}
- 英文标签: {wd_fields["label_en"]}
- 描述: {wd_fields["description_zh"]}
- 已知异称: {", ".join(wd_fields["aliases_zh"]) or "(无)"}
- 生年: {wd_fields["birth"] or "?"}
- 卒年: {wd_fields["death"] or "?"}"""

            print(f"  → LLM 加工 ({LLM_MODEL})...", end=" ", flush=True)
            figure = generate_figure(name, material)
            figure["source"] = "wikipedia+wikidata"
            figure["wikidata_id"] = qid
            print("OK")

            figures.append(figure)
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {e}")
            figures.append({"name": name, "wikidata_id": qid, "error": str(e)})

    OUTPUT_PATH.write_text(
        json.dumps(figures, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ 输出已保存: {OUTPUT_PATH}")
    print("\n请人工审核以下维度（详见 README.md）：")
    print("  - 事实准确性（年份、官职、籍贯、作品归属）")
    print("  - 难度梯度（1 最难、7 最易，递进合理？）")
    print("  - 难度 1 关键约束：不含人名/朝代/著名作品名")
    print("  - 异称完整度（字、号、谥号、庙号是否齐全）")
    print("  - clue 文字（30-60 字、单句、无错别字）")


if __name__ == "__main__":
    main()
