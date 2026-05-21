#!/usr/bin/env python3
"""
Batch Generate: 多模型 × 多人物全量跑，prototype A 最终验证。

设计意图（按用户分工）：
- gemini-3.1-flash-lite : 实时对话场景（运行时模糊匹配，要求 < 2s 返回）
- deepseek-v4-flash      : 内容生成场景（离线、reasoning model 深思但慢）

注意：deepseek-v4-flash 在 benchmark 阶段单测就 content 空（reasoning 突破 max_tokens=8000），
5 人跑可能多数 / 全部失败。即便失败，本次跑也作为"两个模型适用性"的实测证据保留。

跑法：python batch_generate.py
输出：
  - figures-{model-id}.json  每模型 1 份，含 5 人成功生成的 figures
  - 控制台末尾 stats 表：每模型的成功率 / 总时间 / 总 token / 总成本 / 平均质量
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
    {"name": "诸葛亮"},  # 三国 / 军政
    {"name": "李白"},    # 唐 / 文学
    {"name": "武则天"},  # 唐 / 帝王
    {"name": "朱元璋"},  # 明 / 帝王
    {"name": "鲁迅"},    # 近代 / 文学
]

MODELS_FOR_BATCH = [
    {"id": "gemini-3.1-flash-lite", "in": 0.375, "out": 2.25, "use_case": "实时对话"},
    {"id": "deepseek-v4-flash",     "in": 1.0,   "out": 2.0,  "use_case": "内容生成"},
]

OUTPUT_DIR = Path(__file__).parent
USER_AGENT = "guess-figure-prototype/0.1 (vibe-coding-lab; batch)"

LLM_API_KEY = os.environ["YUNWU_API_KEY"]
LLM_BASE_URL = os.environ.get("YUNWU_BASE_URL", "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"

WIKIPEDIA = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT, language="zh", extract_format=wikipediaapi.ExtractFormat.WIKI,
)


# ===== 维基 / Wikidata 拉数据（5 人各拉一次，所有模型共享） =====
def search_wikidata_qid(name: str) -> str:
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={"action": "wbsearchentities", "search": name, "language": "zh",
                "format": "json", "type": "item", "limit": 5},
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("search", [])
    if not results:
        raise RuntimeError(f"Wikidata 搜不到 '{name}'")
    return results[0]["id"]


def fetch_wikidata_fields(qid: str) -> dict:
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={"action": "wbgetentities", "ids": qid, "format": "json",
                "languages": "zh|en", "props": "labels|aliases|claims|descriptions"},
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
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


def fetch_material_for(name: str):
    page = WIKIPEDIA.page(name)
    if not page.exists():
        return None, None
    wiki_summary = page.summary[:1000]

    qid = search_wikidata_qid(name)
    time.sleep(1)
    wd = fetch_wikidata_fields(qid)

    material = f"""维基中文摘要：
{wiki_summary}

Wikidata 字段：
- 中文标签: {wd["label_zh"]}
- 英文标签: {wd["label_en"]}
- 描述: {wd["description_zh"]}
- 已知异称: {", ".join(wd["aliases_zh"]) or "(无)"}
- 生年: {wd["birth"] or "?"}
- 卒年: {wd["death"] or "?"}"""
    return material, qid


# ===== Prompt =====
PROMPT_TEMPLATE = """你是中国历史人物题库编辑。我给你 1 位历史人物的原始材料，请你输出严格 JSON 格式的题目数据。

输出 schema：
{{
  "name": "<本名>",
  "aliases": ["<异称1>", "<异称2>", "..."],
  "clues": [
    {{"text": "<难度 1: 最难>", "difficulty": 1}},
    {{"text": "<难度 2>", "difficulty": 2}},
    {{"text": "<难度 3>", "difficulty": 3}},
    {{"text": "<难度 4>", "difficulty": 4}},
    {{"text": "<难度 5: 标准范围内最易>", "difficulty": 5}},
    {{"text": "<难度 6: 求救线索>", "difficulty": 6}},
    {{"text": "<难度 7: 几乎暴露答案>", "difficulty": 7}}
  ]
}}

规则：
1. aliases 必须真实历史记载：字、号、谥号、庙号、别号、绰号。3-5 个。
2. 每条 clue 30-60 字，单句。
3. **难度 1-5 全段绝不出现 aliases 任何字眼**（含姓氏单字），否则等于直接给答案。
4. 难度 1 额外约束：不出现朝代名、不出现最著名作品名、不出现最标志性事件（如"三顾茅庐""杨贵妃""砸缸""陈桥兵变"）。
5. 难度 6-7 可以出现朝代、部分作品名、标志性事件，但仍不出现本名。
6. 用第三人称。
7. 严格输出 JSON，前后无 markdown 代码块标记，无其他说明文字。

原始材料：
{material}

人物中文名：{name}
"""


# ===== LLM 调用 =====
def call_model(model_id: str, prompt: str) -> dict:
    url = f"{LLM_BASE_URL}/chat/completions"
    start = time.monotonic()
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 8000,
            },
            timeout=300,
        )
        elapsed = time.monotonic() - start

        if r.status_code != 200:
            return {"ok": False, "time_s": elapsed, "http_status": r.status_code,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}"}

        data = r.json()
        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        usage = data.get("usage", {}) or {}
        return {
            "ok": bool(content),
            "time_s": elapsed,
            "http_status": 200,
            "content": content,
            "reasoning_len": len(reasoning),
            "finish_reason": choice.get("finish_reason"),
            "usage": usage,
            "error": None if content else f"content 空 (reasoning {len(reasoning)} 字, finish={choice.get('finish_reason')})",
        }
    except Exception as e:
        return {"ok": False, "time_s": time.monotonic() - start,
                "error": f"{type(e).__name__}: {str(e)[:200]}"}


def parse_json(content: str) -> dict:
    text = content.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


# ===== 质量打分 =====
DYNASTY_WORDS = ["夏朝", "商朝", "西周", "东周", "春秋", "战国", "秦朝", "西汉", "东汉",
                 "三国", "蜀汉", "曹魏", "孙吴", "西晋", "东晋", "南北朝", "隋朝", "唐朝",
                 "五代", "北宋", "南宋", "宋朝", "辽朝", "金朝", "元朝", "明朝", "清朝", "民国"]


def quality_score(figure: dict):
    score = 0
    notes = []
    aliases = figure.get("aliases") or []
    clues = figure.get("clues") or []

    if 3 <= len(aliases) <= 5:
        score += 1
    else:
        notes.append(f"aliases数{len(aliases)}≠3-5")

    if len(clues) == 7:
        score += 1
    else:
        notes.append(f"clues数{len(clues)}≠7")

    diffs = sorted([c.get("difficulty") for c in clues if isinstance(c, dict)])
    if diffs == [1, 2, 3, 4, 5, 6, 7]:
        score += 1
    else:
        notes.append(f"难度{diffs}≠[1-7]")

    if aliases and clues:
        leak = None
        for c in clues:
            if isinstance(c, dict) and c.get("difficulty", 0) <= 5:
                text = c.get("text", "")
                for a in aliases:
                    if a and a in text:
                        leak = (c.get("difficulty"), a)
                        break
                if leak:
                    break
        if not leak:
            score += 1
        else:
            notes.append(f"难度{leak[0]}含异称'{leak[1]}'")

    d1 = next((c for c in clues if isinstance(c, dict) and c.get("difficulty") == 1), None)
    if d1:
        text = d1.get("text", "")
        bad = [w for w in DYNASTY_WORDS if w in text]
        if not bad:
            score += 1
        else:
            notes.append(f"难度1含朝代{bad[:2]}")

    return score, notes


# ===== 单模型 × 单人物 流水线 =====
def process_one(model_cfg: dict, name: str, material: str, qid: str) -> dict:
    model_id = model_cfg["id"]
    prompt = PROMPT_TEMPLATE.format(material=material, name=name)

    r = call_model(model_id, prompt)
    figure = None
    parse_err = None
    if r.get("content"):
        try:
            figure = parse_json(r["content"])
            figure["source"] = "wikipedia+wikidata"
            figure["wikidata_id"] = qid
            figure["_model"] = model_id
        except Exception as e:
            parse_err = f"JSON 解析失败: {type(e).__name__}: {str(e)[:150]}"

    usage = r.get("usage") or {}
    in_tok = usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("completion_tokens", 0) or 0
    cost = (in_tok * model_cfg["in"] + out_tok * model_cfg["out"]) / 1_000_000

    if figure:
        score, notes = quality_score(figure)
    elif parse_err:
        score, notes = 0, [parse_err]
    else:
        score, notes = 0, [r.get("error", "未知失败")]

    return {
        "name": name, "ok": figure is not None, "figure": figure,
        "time_s": r["time_s"], "input_tokens": in_tok, "output_tokens": out_tok,
        "reasoning_len": r.get("reasoning_len", 0), "cost_usd": cost,
        "score": score, "notes": notes,
    }


# ===== 报告 =====
def print_summary(all_stats: list):
    print("\n" + "=" * 100)
    print(f"{'模型':<28} {'用途':<10} {'成功':<8} {'总时间':<10} {'总tok in/out':<18} {'总成本$':<10} {'均质量':<8}")
    print("-" * 100)
    for s in all_stats:
        results = s["results"]
        ok = sum(1 for r in results if r["ok"])
        tt = sum(r["time_s"] for r in results)
        ti = sum(r["input_tokens"] for r in results)
        to = sum(r["output_tokens"] for r in results)
        tc = sum(r["cost_usd"] for r in results)
        avg = sum(r["score"] for r in results) / len(results) if results else 0
        n = len(results)
        print(f"{s['model']:<28} {s['use_case']:<10} {ok}/{n:<6} {tt:>6.1f}s   {ti}/{to:<10} ${tc:.5f}   {avg:.1f}/5")
    print("=" * 100)
    print("\n详细每人物 figure 内容：figures-<model-id>.json")
    print("基于 5 人 × 2 模型的结果，给 prototype A 最终评判:")
    print("  ✅ V1 可接受   ⚠️ prompt 还要调   ❌ 必须改架构")


def main():
    print(f"=== 批量生成: {len(MODELS_FOR_BATCH)} 模型 × {len(TEST_FIGURES)} 人物 ===\n")
    print(f"配置: base_url={LLM_BASE_URL}\n")

    # 共享 material（一次性拉，所有模型用）
    print("━━━━ 拉数据（5 人共享）━━━━")
    materials = {}
    for fig in TEST_FIGURES:
        name = fig["name"]
        print(f"  {name}...", end=" ", flush=True)
        try:
            material, qid = fetch_material_for(name)
            if material:
                materials[name] = (material, qid)
                print(f"OK ({qid}, {len(material)} 字)")
            else:
                print("FAIL: 维基无条目")
        except Exception as e:
            print(f"FAIL: {type(e).__name__}: {str(e)[:100]}")
        time.sleep(1)

    if not materials:
        print("\n❌ 所有人物都拉数据失败")
        return

    # 每个模型对全 5 人跑
    all_stats = []
    for model_cfg in MODELS_FOR_BATCH:
        model_id = model_cfg["id"]
        print(f"\n\n████████ 模型: {model_id} ({model_cfg['use_case']}) ████████\n")
        figures = []
        results = []

        for fig in TEST_FIGURES:
            name = fig["name"]
            if name not in materials:
                print(f"  [{name}] 跳过（material 缺）")
                continue
            material, qid = materials[name]
            print(f"  [{name}]", end=" ", flush=True)
            r = process_one(model_cfg, name, material, qid)
            status = "✅" if r["ok"] else "❌"
            tail = f"质量 {r['score']}/5" if r["ok"] else (r["notes"][0][:80] if r["notes"] else "")
            print(f"{status} {r['time_s']:>5.1f}s  {tail}")
            if r["figure"]:
                figures.append(r["figure"])
            results.append(r)

        # 保存
        safe_id = re.sub(r"[^a-z0-9.-]", "-", model_id.lower())
        out_path = OUTPUT_DIR / f"figures-{safe_id}.json"
        out_path.write_text(json.dumps(figures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  → 保存 {len(figures)}/{len(results)} 成功 figures: {out_path.name}")

        all_stats.append({"model": model_id, "use_case": model_cfg["use_case"], "results": results})

    print_summary(all_stats)


if __name__ == "__main__":
    main()
