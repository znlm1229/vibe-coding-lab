#!/usr/bin/env python3
"""
Prototype pipeline spike (Stage 3, 003-clue-optimization).

最小化端到端 spike: 验证 (1) 强 LLM 候选质量 (2) 二十四史接入 (3) profile 中间层 (4) judge 单跑。
本 spike 不实现自动循环重试 — 那是 production 实现细节。

用法:
  python scripts/proto_pipeline.py --figure 诸葛亮 --strong-llm claude-haiku-4-5-20251001 --wikisource 三國志/卷35
  python scripts/proto_pipeline.py --figure 诸葛亮 --strong-llm gemini-2.5-pro --wikisource 三國志/卷35
  python scripts/proto_pipeline.py --figure 诸葛亮 --strong-llm deepseek-v3.2 --wikisource 三國志/卷35

输出: workflow/003-clue-optimization/proto/run-{model-tag}/
  - material.txt       三源材料拼接 (维基 + Wikidata + 二十四史)
  - profile.md         强 LLM 产的画像
  - clues.json         flash-lite 产的 7 条 clues
  - judge.json         flash-lite judge verdict
  - cost.json          token / 成本 / 时间明细
"""

import argparse, json, os, re, sys, time
from pathlib import Path
import requests
import wikipediaapi
from dotenv import load_dotenv

# 强制 stdout 用 UTF-8 (Windows console 默认 GBK, 中文 log 乱码)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
LLM_KEY = os.environ.get("YUNWU_API_KEY")
LLM_BASE = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE.endswith("/v1"):
    LLM_BASE += "/v1"
FLASH = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
UA = "guess-figure-proto/0.1 (vibe-coding-lab; 003-prototype)"

WIKI = wikipediaapi.Wikipedia(user_agent=UA, language="zh", extract_format=wikipediaapi.ExtractFormat.WIKI)


def fetch_wiki_full(name: str) -> str | None:
    """维基中文全文(截 5000 字)。"""
    page = WIKI.page(name)
    if not page.exists():
        return None
    return (page.text or "")[:5000]


def fetch_wikidata_basic(name: str) -> dict | None:
    """Wikidata 现有 6 字段 (prototype 简化)。SPEC 阶段扩到 15 字段。"""
    r = requests.get("https://www.wikidata.org/w/api.php",
                     params={"action": "wbsearchentities", "search": name, "language": "zh",
                             "format": "json", "type": "item", "limit": 5},
                     headers={"User-Agent": UA}, timeout=30)
    results = r.json().get("search", [])
    if not results:
        return None
    qid = results[0]["id"]
    r2 = requests.get("https://www.wikidata.org/w/api.php",
                      params={"action": "wbgetentities", "ids": qid, "format": "json",
                              "languages": "zh|en", "props": "labels|aliases|claims|descriptions"},
                      headers={"User-Agent": UA}, timeout=30)
    ent = r2.json()["entities"][qid]
    claims = ent.get("claims", {})
    def get_time(prop):
        try: return claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"]
        except (KeyError, IndexError, TypeError): return None
    return {
        "qid": qid,
        "label_zh": ent.get("labels", {}).get("zh", {}).get("value", ""),
        "label_en": ent.get("labels", {}).get("en", {}).get("value", ""),
        "description_zh": ent.get("descriptions", {}).get("zh", {}).get("value", ""),
        "aliases_zh": [a["value"] for a in ent.get("aliases", {}).get("zh", [])],
        "birth": get_time("P569"),
        "death": get_time("P570"),
    }


def fetch_wikisource(page_name: str) -> str | None:
    """从 Wikisource 拉某二十四史本传, 截 5000 字, 简单清 wiki markup。"""
    if not page_name:
        return None
    r = requests.get("https://zh.wikisource.org/w/api.php",
                     params={"action": "parse", "page": page_name, "format": "json", "prop": "wikitext"},
                     headers={"User-Agent": UA}, timeout=60)
    if r.status_code != 200:
        return None
    data = r.json()
    if "error" in data:
        return None
    wt = data.get("parse", {}).get("wikitext", {}).get("*", "")
    # 简化清理: 去 ref / 模板 / link 标记
    wt = re.sub(r"<ref[^>]*>.*?</ref>", "", wt, flags=re.DOTALL)
    wt = re.sub(r"<ref[^>]*/>", "", wt)
    wt = re.sub(r"\{\{[^}]+\}\}", "", wt)
    wt = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", wt)
    wt = re.sub(r"'{2,5}", "", wt)
    wt = re.sub(r"\n{3,}", "\n\n", wt)
    return wt.strip()[:5000]


def call_llm(model: str, system: str, user: str, temperature: float = 0.3, max_tokens: int = 4000) -> dict:
    t0 = time.time()
    r = requests.post(f"{LLM_BASE}/chat/completions",
                      headers={"Authorization": f"Bearer {LLM_KEY}",
                               "Content-Type": "application/json"},
                      json={"model": model,
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
                            "temperature": temperature,
                            "max_tokens": max_tokens},
                      timeout=300)
    latency = round(time.time() - t0, 2)
    r.raise_for_status()
    data = r.json()
    choice = data["choices"][0]
    return {
        "model": model,
        "content": choice["message"].get("content") or "",
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage", {}),
        "latency_s": latency,
    }


PROFILE_PROMPT = """你是中国历史人物 profile 编辑。给你 1 位历史人物的三源原始材料(维基中文全文 + Wikidata 字段 + 二十四史本传选段),输出一份**结构化的人物画像 markdown**。

输出格式 (严格按 8 sections,不增删):

# {name}

## 基本信息
- 字 / 号 / 谥号 / 庙号 / 别号: <列出所有,无则填"无">
- 生卒年 / 朝代区间 / 籍贯: <...>
- 主要职业 / 身份: <...>

## 主要事迹
(5-10 件,按时间序,每条结尾标 [重要]/[一般]/[次要])
- ...

## 性格 / 风格特征
(2-4 条,源自史料记载,不要泛泛而论)
- ...

## 典故 / 标志事件
(3-5 个,每个 1 句话,这些后续用作 d1-5 banlist)
- ...

## 关键作品
(3-5 个,文学/著作/政绩等)
- ...

## 关系网
- 老师 / 同辈 / 弟子 / 政敌 / 家人 (各列 1-3 人,标关系类型)
- ...

## 历史评价
- 正面: <...>
- 负面: <...>
- 后世神话/演义: <...>

## 反差 / 鲜为人知点
(1-3 个,这是 d1 难线索的源,必须是不在维基主条目首段的隐晦信息)
- ...

规则:
1. 严格按 8 个 section,不增不减
2. "典故 / 标志事件" 是后续 d1-5 线索的 banlist,要列得**完整准确**
3. "反差 / 鲜为人知点" 是 d1 难线索的源,必须是普通人不知道的反差面
4. 文字简洁,单点 1 句话
5. 输出纯 markdown,无 ``` 包裹
"""

CLUE_PROMPT = """你是中国历史人物题目编辑。给你 1 位历史人物的 profile (结构化画像),凝结 7 条难度梯度递增的猜谜线索。

输出 JSON schema (严格,无 ``` 包裹):
{{
  "name": "<画像 name>",
  "aliases": [<画像基本信息列出的字/号/谥号/庙号/别号,5-8 个>],
  "clues": [
    {{"text": "<难度 1 — 最难,30-60 字>", "difficulty": 1}},
    {{"text": "<难度 2>", "difficulty": 2}},
    {{"text": "<难度 3>", "difficulty": 3}},
    {{"text": "<难度 4>", "difficulty": 4}},
    {{"text": "<难度 5 — 标准范围最易>", "difficulty": 5}},
    {{"text": "<难度 6 — 求救范围>", "difficulty": 6}},
    {{"text": "<难度 7 — 求救范围,几乎暴露>", "difficulty": 7}}
  ]
}}

难度规则:

**d1 (最难)** 必做:
- 只引用画像「反差 / 鲜为人知点」section 的 1-2 条内容
- 让普通人脱离朝代/作品/典故后,只能凭隐晦反差去猜
**d1 禁做**:
- 含画像「典故 / 标志事件」section 任何字眼
- 含画像「关键作品」section 任何字眼
- 含 aliases 任一字符 (整字 + 子串)
- 含朝代名 (汉/唐/宋/明/清/三国/秦/晋/隋/元 等)

**d2 (次难)**:
- 可触历史评价的最抽象描述
- d1 禁做规则除朝代名外仍适用

**d3**:
- 可触关系网的抽象描述
- d1 禁做规则除朝代名外仍适用

**d4-d5**:
- 可间接指代作品/典故 (不出具体名)
- 仍不含 aliases 字符

**d6 (求救范围)**:
- 可触朝代 / 作品名 / 标志事件
- 禁 aliases (整字 + 子串都禁)

**d7 (求救范围,几乎暴露)**:
- 同 d6,且禁 "字/号/谥号/庙号" 等关键字 + aliases 字符

通用:
- 每条 clue 单句,30-60 字,第三人称

常见 d1 反例 (勿模仿):
- 乾隆 d1 "暮年自诩拥有十项武功" — 语义 ≈ alias「十全老人」
- 关羽 d7 "字云长,河东解人" — alias 子串穿底
- 刘备 d2 "以织席贩履为业,与两位结义兄弟" — 标志事件穿底

人物 profile:
{profile}
"""

JUDGE_PROMPT = """你是中国历史人物线索质量审稿员。给定 aliases + 画像「典故 / 关键作品」section + 7 条 clues,为每条 clue 输出 verdict ("合规" / "可疑" / "违规") + 理由。

verdict 标准:

**违规** (任一触发即违规):
- clue 含 aliases 任一整字 (任难度)
- clue 含 aliases 子串 (d1-5)
- clue 含 banlist 中典故/作品名 (d1-d5)
- d1 含朝代名

**可疑** (软违规):
- clue 太短 (< 20 字) / 太长 (> 80 字)
- 难度梯度与编号不符 (如 d1 比 d5 更具体)
- 信息密度异常 (d1 出现 ≥ 4 个专有名词)

**合规**: 否则

输出 JSON (无 ``` 包裹):
{{
  "verdicts": [
    {{"d": 1, "verdict": "<合规/可疑/违规>", "reason": "..."}},
    ...
  ]
}}

人物 aliases: {aliases}

banlist (典故 + 关键作品):
{banlist}

7 条 clues:
{clues}
"""


def main():
    parser = argparse.ArgumentParser(description="Prototype pipeline spike (003)")
    parser.add_argument("--figure", required=True, help='figure 名 (如 "诸葛亮")')
    parser.add_argument("--strong-llm", required=True, help='强 LLM model id (云雾)')
    parser.add_argument("--wikisource", default=None, help='二十四史 Wikisource 页名 (如 "三國志/卷35"),省略则不拉')
    parser.add_argument("--output-dir", default=None, help='输出目录')
    args = parser.parse_args()

    if not LLM_KEY:
        raise SystemExit("❌ 缺 YUNWU_API_KEY 环境变量")

    name = args.figure
    strong = args.strong_llm
    # 简化的 model tag (取前 2 段) 用于目录命名
    parts = strong.split("-")
    model_tag = "-".join(parts[:3]) if len(parts) >= 3 else strong
    model_tag = re.sub(r"[^\w\-]", "_", model_tag)
    out = Path(args.output_dir) if args.output_dir else (
        PROJECT_ROOT / "workflow" / "003-clue-optimization" / "proto" / f"run-{model_tag}"
    )
    out.mkdir(parents=True, exist_ok=True)

    cost = {"figure": name, "strong_model": strong, "flash_model": FLASH, "wikisource": args.wikisource, "calls": []}
    t_total = time.time()

    # ===== Step 1: fetch 三源 =====
    print(f"\n=== Step 1: fetch 三源材料 ({name}) ===")
    wiki = fetch_wiki_full(name)
    if not wiki:
        raise SystemExit(f"❌ 维基中文无 '{name}' 条目")
    print(f"  维基: {len(wiki)} 字")

    wd = fetch_wikidata_basic(name)
    if not wd:
        print("  ⚠️ Wikidata 拉不到, 继续")
    else:
        print(f"  Wikidata: {len(wd)} 字段 ({wd.get('qid')})")

    time.sleep(1)
    history = fetch_wikisource(args.wikisource) if args.wikisource else None
    if args.wikisource:
        print(f"  二十四史 ({args.wikisource}): {len(history) if history else 0} 字")
        if not history:
            print("  ⚠️ Wikisource 拉不到 / page 不存在, 走 fallback (仅维基+Wikidata)")
    else:
        print("  二十四史: (未提供 --wikisource, 走 fallback)")

    material = f"## 维基中文 (~5000 字)\n{wiki}\n"
    if wd:
        material += f"\n## Wikidata 基础字段\n{json.dumps(wd, ensure_ascii=False, indent=2)}\n"
    if history:
        material += f"\n## 二十四史本传 ({args.wikisource}, 简单清后 ~5000 字)\n{history}\n"
    (out / "material.txt").write_text(material, encoding="utf-8")
    cost["material_chars"] = len(material)

    # ===== Step 2: 强 LLM 产 profile =====
    print(f"\n=== Step 2: 强 LLM ({strong}) 产 profile ===")
    sys_p = "你是严谨的中国历史人物 profile 编辑。"
    res = call_llm(strong, sys_p, PROFILE_PROMPT.format(name=name) + "\n\n材料:\n" + material,
                   temperature=0.3, max_tokens=4000)
    profile = res["content"]
    (out / "profile.md").write_text(profile, encoding="utf-8")
    cost["calls"].append({"step": "profile", **{k: res[k] for k in ("model", "usage", "latency_s", "finish_reason")}})
    print(f"  ✓ profile {len(profile)} 字 ({res['latency_s']}s, usage={res['usage']})")
    if res["finish_reason"] == "length":
        print("  ⚠️ profile 被 max_tokens 截断, 后续可能不完整")

    # ===== Step 3: flash-lite 产 clues =====
    print(f"\n=== Step 3: flash-lite ({FLASH}) 产 clues ===")
    res = call_llm(FLASH, "你是严谨的中国历史人物题目编辑, 严格按 JSON 输出。",
                   CLUE_PROMPT.format(profile=profile), temperature=0.3, max_tokens=2000)
    raw = res["content"].strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw)
        raw = re.sub(r"\n```\s*$", "", raw)
    try:
        clues_obj = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ❌ clues JSON parse 失败: {e}\n  raw 前 300: {raw[:300]}")
        (out / "clues_raw.txt").write_text(raw, encoding="utf-8")
        cost["calls"].append({"step": "clue", "error": str(e), **{k: res[k] for k in ("model", "usage", "latency_s")}})
        (out / "cost.json").write_text(json.dumps(cost, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.exit(2)
    (out / "clues.json").write_text(json.dumps(clues_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    cost["calls"].append({"step": "clue", **{k: res[k] for k in ("model", "usage", "latency_s", "finish_reason")}})
    print(f"  ✓ {len(clues_obj.get('clues', []))} 条 ({res['latency_s']}s)")
    for c in clues_obj.get("clues", []):
        print(f"    d{c['difficulty']}: {c['text']}")

    # ===== Step 4: flash-lite judge =====
    print(f"\n=== Step 4: flash-lite judge ===")
    # 从 profile 抽 typology + works 作 banlist
    banlist_parts = []
    for hdr in ["典故 / 标志事件", "关键作品"]:
        m = re.search(rf"^##\s+{re.escape(hdr)}\s*\n((?:[-*]\s*.+\n?)+)", profile, flags=re.MULTILINE)
        if m:
            banlist_parts.append(f"### {hdr}\n{m.group(1).rstrip()}")
    banlist = "\n\n".join(banlist_parts) if banlist_parts else "(profile 未抽出 banlist)"
    clues_text = "\n".join(f"d{c['difficulty']}: {c['text']}" for c in clues_obj.get("clues", []))
    aliases_text = ", ".join(clues_obj.get("aliases", []))

    res = call_llm(FLASH, "你是严谨的题目质量审稿员, 严格按 JSON 输出。",
                   JUDGE_PROMPT.format(aliases=aliases_text, banlist=banlist, clues=clues_text),
                   temperature=0.1, max_tokens=2000)
    raw = res["content"].strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n", "", raw)
        raw = re.sub(r"\n```\s*$", "", raw)
    try:
        judge_obj = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ❌ judge JSON parse 失败: {e}")
        (out / "judge_raw.txt").write_text(raw, encoding="utf-8")
        judge_obj = {"verdicts": [], "parse_failed": True, "error": str(e)}
    (out / "judge.json").write_text(json.dumps(judge_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    cost["calls"].append({"step": "judge", **{k: res[k] for k in ("model", "usage", "latency_s", "finish_reason")}})
    print(f"  ✓ judge done ({res['latency_s']}s)")
    if "verdicts" in judge_obj and judge_obj["verdicts"]:
        violations = sum(1 for v in judge_obj["verdicts"] if v.get("verdict") == "违规")
        suspicious = sum(1 for v in judge_obj["verdicts"] if v.get("verdict") == "可疑")
        ok = sum(1 for v in judge_obj["verdicts"] if v.get("verdict") == "合规")
        print(f"  verdict: {ok} 合规 / {suspicious} 可疑 / {violations} 违规")
        for v in judge_obj["verdicts"]:
            icon = {"合规": "✓", "可疑": "?", "违规": "✗"}.get(v.get("verdict"), "?")
            print(f"    {icon} d{v.get('d')}: {v.get('verdict')} — {(v.get('reason') or '')[:80]}")

    # ===== Cost summary =====
    cost["total_latency_s"] = round(time.time() - t_total, 2)
    (out / "cost.json").write_text(json.dumps(cost, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 完成 (总耗时 {cost['total_latency_s']}s) ===")
    print(f"输出: {out}")


if __name__ == "__main__":
    main()
