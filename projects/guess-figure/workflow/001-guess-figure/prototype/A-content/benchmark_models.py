#!/usr/bin/env python3
"""
Benchmark: 多模型并行跑同一测试人物 + 报告时间/token/成本/质量，辅助选型。

固定测试人物 = 诸葛亮（已有 baseline，便于横向对比）。
6 个候选模型并行调用（独立线程），失败隔离。

跑法：python benchmark_models.py
输出：
  - 控制台报告表格（按质量分排序）
  - 每个模型的输出 JSON：proto-<model-id>.json
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import wikipediaapi
from dotenv import load_dotenv

load_dotenv()

# ===== 配置 =====
TEST_NAME = "诸葛亮"
OUTPUT_DIR = Path(__file__).parent
USER_AGENT = "guess-figure-prototype/0.1 (vibe-coding-lab; benchmark)"

# 6 个候选模型 + 价格表（$/M token，来自云雾截图，如有出入按云雾实际为准）
# 类型说明：reasoning = 有"思考"阶段（慢 + 贵）；chat = 标准对话模型
MODELS = [
    {"id": "gpt-5.4-nano",             "in": 0.12,  "out": 0.75,  "type": "chat"},
    {"id": "gpt-5.4-mini",             "in": 0.45,  "out": 2.7,   "type": "chat"},
    {"id": "gemini-3.1-flash-lite",    "in": 0.375, "out": 2.25,  "type": "chat"},
    {"id": "gemini-3.5-flash",         "in": 2.25,  "out": 13.5,  "type": "chat"},
    {"id": "glm-4.7",     "in": 0.3,   "out": 3.0,   "type": "?"},
    {"id": "deepseek-v4-flash",        "in": 1.0,   "out": 2.0,   "type": "reasoning"},
]

LLM_API_KEY = os.environ["YUNWU_API_KEY"]
LLM_BASE_URL = os.environ.get("YUNWU_BASE_URL", "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"

WIKIPEDIA = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT,
    language="zh",
    extract_format=wikipediaapi.ExtractFormat.WIKI,
)


# ===== 共享数据拉取（只跑一次，所有模型共用 material） =====
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


def fetch_material(name: str):
    """所有模型共享同一份 material，避免重复爬维基。"""
    print(f"━━━ 拉数据 ({name}) ━━━")
    print("  维基中文...", end=" ", flush=True)
    page = WIKIPEDIA.page(name)
    if not page.exists():
        raise RuntimeError(f"维基无 {name}")
    wiki_summary = page.summary[:1000]
    print(f"OK ({len(wiki_summary)} 字)")

    print("  Wikidata 搜 QID...", end=" ", flush=True)
    qid = search_wikidata_qid(name)
    print(f"OK ({qid})")
    time.sleep(1)

    print("  Wikidata 字段...", end=" ", flush=True)
    wd = fetch_wikidata_fields(qid)
    print("OK\n")

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
4. 难度 1 额外约束：不出现朝代名、不出现最著名作品名、不出现最标志性事件。
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
                    "error": f"HTTP {r.status_code}: {r.text[:300]}"}

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
            "error": None if content else "content 为空",
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


# ===== 质量打分（机器可校验，0-5 分） =====
DYNASTY_WORDS = ["夏", "商", "周", "秦", "汉", "三国", "魏", "蜀", "吴", "晋",
                 "南北朝", "隋", "唐", "宋", "元", "明", "清", "民国"]


def quality_score(figure: dict):
    """机器可校验的 5 项质量检测。返回 (score, notes)"""
    score = 0
    notes = []
    aliases = figure.get("aliases") or []
    clues = figure.get("clues") or []

    # 1. aliases 数 3-5
    if 3 <= len(aliases) <= 5:
        score += 1
    else:
        notes.append(f"aliases数{len(aliases)}≠3-5")

    # 2. clues 数 = 7
    if len(clues) == 7:
        score += 1
    else:
        notes.append(f"clues数{len(clues)}≠7")

    # 3. difficulty 1-7 各 1 个
    diffs = sorted([c.get("difficulty") for c in clues if isinstance(c, dict)])
    if diffs == [1, 2, 3, 4, 5, 6, 7]:
        score += 1
    else:
        notes.append(f"难度{diffs}≠[1-7]")

    # 4. 难度 1-5 不含 aliases 任何字眼（最关键约束）
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

    # 5. 难度 1 不含朝代名
    d1 = next((c for c in clues if isinstance(c, dict) and c.get("difficulty") == 1), None)
    if d1:
        text = d1.get("text", "")
        bad = [w for w in DYNASTY_WORDS if w in text]
        if not bad:
            score += 1
        else:
            notes.append(f"难度1含朝代{bad}")

    return score, notes


# ===== 单模型完整流程 =====
def benchmark_model(model_cfg: dict, material: str, name: str, qid: str) -> dict:
    model_id = model_cfg["id"]
    prompt = PROMPT_TEMPLATE.format(material=material, name=name)

    result = call_model(model_id, prompt)

    figure = None
    parse_err = None
    if result.get("content"):
        try:
            figure = parse_json(result["content"])
            figure["source"] = "wikipedia+wikidata"
            figure["wikidata_id"] = qid
            figure["_model"] = model_id
        except Exception as e:
            parse_err = f"JSON解析失败: {type(e).__name__}: {str(e)[:150]}"

    usage = result.get("usage") or {}
    in_tok = usage.get("prompt_tokens", 0) or 0
    out_tok = usage.get("completion_tokens", 0) or 0
    cost = (in_tok * model_cfg["in"] + out_tok * model_cfg["out"]) / 1_000_000

    if figure:
        score, notes = quality_score(figure)
    elif parse_err:
        score, notes = 0, [parse_err]
    else:
        score, notes = 0, [result.get("error", "未知失败")]

    if figure:
        safe_id = re.sub(r"[^a-z0-9.-]", "-", model_id.lower())
        out_path = OUTPUT_DIR / f"proto-{safe_id}.json"
        out_path.write_text(json.dumps(figure, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "model": model_id,
        "type": model_cfg["type"],
        "ok": result["ok"] and figure is not None,
        "time_s": result["time_s"],
        "http_status": result.get("http_status", "?"),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "reasoning_len": result.get("reasoning_len", 0),
        "finish_reason": result.get("finish_reason", "?"),
        "cost_usd": cost,
        "score": score,
        "notes": notes,
    }


# ===== 报告 =====
def print_report(results: list):
    print("\n" + "=" * 110)
    print(f"{'模型':<26} {'类型':<10} {'状态':<6} {'时间':<8} {'in/out tok':<14} {'成本$':<10} {'质量':<6} {'备注'}")
    print("-" * 110)
    for r in sorted(results, key=lambda x: (-x["score"], x["time_s"])):
        status = "✅" if r["ok"] else "❌"
        time_s = f"{r['time_s']:.1f}s"
        tokens = f"{r['input_tokens']}/{r['output_tokens']}"
        if r["reasoning_len"]:
            tokens += f"+R{r['reasoning_len']}"
        cost = f"${r['cost_usd']:.5f}"
        score = f"{r['score']}/5"
        notes = "; ".join(r["notes"][:2]) if r["notes"] else ""
        print(f"{r['model']:<26} {r['type']:<10} {status:<6} {time_s:<8} {tokens:<14} {cost:<10} {score:<6} {notes[:45]}")
    print("=" * 110)
    print("""
说明:
  - 时间      : 单次请求耗时（含 reasoning 阶段）
  - in/out tok: input/output token，+R 后是 reasoning_content 字数（reasoning model）
  - 成本$     : 按云雾价格表估算的单次成本（USD）
  - 质量 X/5  : 机器可校验项打分（aliases数 / clues数 / 难度齐 / 难度1-5不含异称 / 难度1不含朝代）
  - 备注      : 失败原因 或 质量扣分项
""")
    print("详细 JSON 输出：proto-<model-id>.json（每个成功模型一份），可肉眼对比哪家文笔更合你口味")
    print("基于本表 + 内容文笔，挑一个改到 .env 的 LLM_MODEL")


def main():
    print(f"=== Benchmark: {len(MODELS)} 个模型对比，测试人物 = '{TEST_NAME}' ===\n")
    print(f"配置: base_url={LLM_BASE_URL}\n")

    material, qid = fetch_material(TEST_NAME)
    print(f"━━━ 开始并行测 {len(MODELS)} 个模型（独立线程，失败隔离）━━━\n")

    results = []
    with ThreadPoolExecutor(max_workers=len(MODELS)) as ex:
        futures = {ex.submit(benchmark_model, m, material, TEST_NAME, qid): m for m in MODELS}
        for fut in as_completed(futures):
            m = futures[fut]
            try:
                r = fut.result()
                status = "✅" if r["ok"] else "❌"
                tail = f"质量{r['score']}/5" if r["ok"] else (r["notes"][0] if r["notes"] else "?")
                print(f"  {status} {m['id']:<26} {r['time_s']:>6.1f}s  {tail}")
                results.append(r)
            except Exception as e:
                print(f"  ❌ {m['id']:<26} 异常 {type(e).__name__}: {str(e)[:100]}")
                results.append({
                    "model": m["id"], "type": m["type"], "ok": False, "time_s": 0,
                    "input_tokens": 0, "output_tokens": 0, "reasoning_len": 0,
                    "cost_usd": 0, "score": 0, "notes": [str(e)[:100]],
                    "http_status": "?", "finish_reason": "?",
                })

    print_report(results)


if __name__ == "__main__":
    main()
