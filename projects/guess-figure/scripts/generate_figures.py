#!/usr/bin/env python3
"""
内容生产 pipeline v2 (003 任务, T7-T13)。

v2 升级 (相对 v1):
- 3 步 LLM pipeline: 强 LLM 产 profile → flash 产 clues (inject banlist + few-shot) → flash judge → 自动重试 N=2
- 输入侧扩材料: 维基中文全文 5000 字 + Wikidata 6 字段 + 二十四史 Wikisource (按 history_index.json mapping)
- thinking model 防御 (reasoning_tokens > 0 + content 空 → raise)
- profile 入 git: src/lib/data/profiles/{figure_id}.md
- cost cap (¥10 硬上限) + cost_summary.json
- failed_figures.json 记录 N 次重试仍违规的 figure

跑法:
  # 单 figure 测试
  python scripts/generate_figures.py --names "诸葛亮" --strong-llm deepseek-v3.2

  # 多 figure batch
  python scripts/generate_figures.py --names "诸葛亮,苏轼,李白" --strong-llm deepseek-v3.2

  # 全 50 旧 figure 重生成
  python scripts/generate_figures.py --names-from src/lib/data/figures.json --strong-llm deepseek-v3.2 \\
    --output scripts/data/figures.v2-candidates.json

输出:
- figures JSON (--output, 默认 figures-new.json) — 包含 7 条 clues + aliases (schema 同 V1)
- src/lib/data/profiles/{id}.md — 8 sections 结构化画像
- scripts/data/failed_figures.json — N 重试仍失败的 figure
- scripts/data/cost_summary.json — token / 成本累积
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import requests
import wikipediaapi
from dotenv import load_dotenv

# 强制 stdout UTF-8 (Windows console 中文 log)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# Reuse quality_check.py 的 extract_banlist_from_profile + judge_clues_llm
sys.path.insert(0, str(Path(__file__).parent))
from quality_check import extract_banlist_from_profile, judge_clues_llm  # noqa: E402

# ===== 配置 =====
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
DEFAULT_OUTPUT = PROJECT_ROOT / "figures-new.json"
PROFILES_DIR = PROJECT_ROOT / "src" / "lib" / "data" / "profiles"
HISTORY_INDEX = SCRIPTS_DIR / "data" / "history_index.json"
FEW_SHOT_POOL = SCRIPTS_DIR / "few_shot_examples.md"
FAILED_FIGURES = SCRIPTS_DIR / "data" / "failed_figures.json"
COST_SUMMARY = SCRIPTS_DIR / "data" / "cost_summary.json"
LOG_DIR = SCRIPTS_DIR / "logs"
USER_AGENT = "guess-figure/2.0 (vibe-coding-lab; 003-pipeline)"

LLM_API_KEY = os.environ.get("YUNWU_API_KEY")
LLM_BASE_URL = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"
FLASH_MODEL_DEFAULT = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")

# 成本 hard cap (¥, 触发 abort)
COST_HARD_CAP_CNY = 10.0
# 单 LLM 调用粗估单价 (¥/1K tokens), SPEC 阶段调
COST_RATE = {
    # deepseek 系: 便宜 (云雾约 $0.5/M in, $1.5/M out → 人民币 ¥3.5/M in, ¥10.5/M out)
    "deepseek": {"in": 3.5e-6, "out": 10.5e-6},
    # claude-haiku: $1/M in, $5/M out → ¥7/M in, ¥35/M out
    "claude-haiku": {"in": 7e-6, "out": 35e-6},
    # gpt-4o-mini, gpt-4.1-mini 等 ≈ haiku
    "gpt": {"in": 7e-6, "out": 35e-6},
    # flash 极便宜 (gemini-flash-lite 单次 ~¥0.0005)
    "gemini": {"in": 0.5e-6, "out": 2e-6},
    # 默认 (兜底, 中性估算)
    "default": {"in": 5e-6, "out": 15e-6},
}

WIKIPEDIA = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT,
    language="zh",
    extract_format=wikipediaapi.ExtractFormat.WIKI,
)


# ===== Logging =====
def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"generate_{time.strftime('%Y%m%d_%H%M%S')}.log"
    logger = logging.getLogger("generate_figures")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    logger.info(f"日志写入: {log_file}")
    return logger


# ===== T7: fetch_three_sources =====
def _wikidata_get_with_retry(params: dict, log: logging.Logger | None = None, max_retries: int = 2) -> dict:
    """Wikidata API GET 含 429 retry (cool down 30s/60s)。"""
    last_err = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 30 * attempt
            if log:
                log.warning(f"  ↻ Wikidata 429 cool down {wait}s 后 retry ({attempt}/{max_retries})")
            time.sleep(wait)
        try:
            r = requests.get(
                "https://www.wikidata.org/w/api.php",
                params=params,
                headers={"User-Agent": USER_AGENT}, timeout=30,
            )
            if r.status_code == 429:
                last_err = "HTTP 429 Too Many Requests"
                continue
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                last_err = "HTTP 429"
                continue
            raise
    raise RuntimeError(f"Wikidata 重试 {max_retries + 1} 次仍 429: {last_err}")


def search_wikidata_qid(name: str, log: logging.Logger | None = None) -> str | None:
    data = _wikidata_get_with_retry(
        {"action": "wbsearchentities", "search": name, "language": "zh",
         "format": "json", "type": "item", "limit": 5}, log=log)
    results = data.get("search", [])
    return results[0]["id"] if results else None


def fetch_wikidata_fields(qid: str, log: logging.Logger | None = None) -> dict:
    data = _wikidata_get_with_retry(
        {"action": "wbgetentities", "ids": qid, "format": "json",
         "languages": "zh|en", "props": "labels|aliases|claims|descriptions"}, log=log)
    entity = data["entities"][qid]
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


def fetch_wikisource_history(page_name: str, log: logging.Logger) -> str | None:
    """从 Wikisource 拉某二十四史本传, 截 5000 字, 简单清 wiki markup。"""
    if not page_name:
        return None
    try:
        r = requests.get(
            "https://zh.wikisource.org/w/api.php",
            params={"action": "parse", "page": page_name, "format": "json",
                    "prop": "wikitext", "redirects": "true"},
            headers={"User-Agent": USER_AGENT}, timeout=60,
        )
        if r.status_code != 200:
            log.warning(f"  ⚠️ Wikisource HTTP {r.status_code}: {page_name}")
            return None
        data = r.json()
        if "error" in data:
            log.warning(f"  ⚠️ Wikisource error: {data['error'].get('info')}")
            return None
        wt = data.get("parse", {}).get("wikitext", {}).get("*", "")
        if len(wt) < 100:
            log.warning(f"  ⚠️ Wikisource page 太短 (len={len(wt)}): {page_name}")
            return None
        # 简单清 markup
        wt = re.sub(r"<ref[^>]*>.*?</ref>", "", wt, flags=re.DOTALL)
        wt = re.sub(r"<ref[^>]*/>", "", wt)
        wt = re.sub(r"\{\{[^}]+\}\}", "", wt)
        wt = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", wt)
        wt = re.sub(r"'{2,5}", "", wt)
        wt = re.sub(r"\n{3,}", "\n\n", wt)
        return wt.strip()[:5000]
    except Exception as e:
        log.warning(f"  ⚠️ Wikisource fetch 异常: {type(e).__name__}: {str(e)[:80]}")
        return None


def fetch_three_sources(name: str, history_mapping: dict | None, log: logging.Logger) -> tuple[dict | None, str | None]:
    """三源 fetch: 维基中文全文 5000 字 + Wikidata 6 字段 + 二十四史本传 (按 mapping).

    返回 (material_dict, qid). material_dict 含 wiki/wikidata/history 三 key.
    """
    log.info(f"  fetch 三源材料 ({name})...")
    # 1. 维基中文全文
    page = WIKIPEDIA.page(name)
    if not page.exists():
        log.warning(f"  ⚠️ 维基中文无 '{name}'")
        return None, None
    wiki_text = (page.text or "")[:5000]
    log.debug(f"  维基: {len(wiki_text)} 字")

    # 2. Wikidata 6 字段 (含 429 retry)
    qid = search_wikidata_qid(name, log=log)
    if not qid:
        log.warning(f"  ⚠️ Wikidata 无 '{name}'")
        wd = None
    else:
        time.sleep(1)
        wd = fetch_wikidata_fields(qid, log=log)
        log.debug(f"  Wikidata: {qid}")

    # 3. 二十四史本传 (按 mapping)
    history_text = None
    wikisource_page = None
    if history_mapping:
        wikisource_page = history_mapping.get("wikisource_page")
        if wikisource_page:
            history_text = fetch_wikisource_history(wikisource_page, log)
            if history_text:
                log.debug(f"  二十四史 ({wikisource_page}): {len(history_text)} 字")
            else:
                log.info(f"  二十四史 fallback: 拉不到 {wikisource_page}, 仅维基+Wikidata")

    material = {
        "wiki": wiki_text,
        "wikidata": wd,
        "history": history_text,
        "history_page": wikisource_page,
    }
    return material, qid


# ===== T8: build_profile (强 LLM + thinking model 防御) =====

PROFILE_PROMPT = """你是中国历史人物 profile 编辑。给你 1 位历史人物的三源原始材料(维基中文全文 + Wikidata 字段 + 可选的二十四史本传选段),输出一份**结构化的人物画像 markdown**。

输出格式 (严格按 8 sections,不增删):

# {name}

## 基本信息
- 字 / 号 / 谥号 / 庙号 / 别号: <列出所有,无则填"无">
- 生卒年 / 朝代区间 / 籍贯: <...>
- 主要职业 / 身份: <...>

## 主要事迹
(5-10 件, 按时间序, 每条结尾标 [重要]/[一般]/[次要])
- ...

## 性格 / 风格特征
(2-4 条, 源自史料记载, 不要泛泛而论)
- ...

## 典故 / 标志事件
(3-5 个, 每个 1 句话, 这些后续用作 d1-5 banlist)
- ...

## 关键作品
(3-5 个, 文学/著作/政绩等)
- ...

## 关系网
- 老师 / 同辈 / 弟子 / 政敌 / 家人 (各列 1-3 人, 标关系类型)
- ...

## 历史评价
- 正面: <...>
- 负面: <...>
- 后世神话/演义: <...>

## 反差 / 鲜为人知点
(1-3 个, 这是 d1 难线索的源, 必须是不在维基主条目首段的隐晦信息)
- ...

规则:
1. 严格按 8 个 section 不增删 (header 格式 `## XXX`)
2. "典故 / 标志事件" 是后续 d1-5 banlist, 要列得**完整准确**
3. "反差 / 鲜为人知点" 是 d1 难线索的源, 必须是普通人不知道的反差面
4. 文字简洁, 单点 1 句话
5. 输出纯 markdown, 无 ``` 包裹
"""


def material_to_text(material: dict) -> str:
    """三源材料 dict → 单一文本喂 LLM."""
    parts = []
    parts.append(f"## 维基中文 (~5000 字)\n{material['wiki']}\n")
    if material.get("wikidata"):
        parts.append(f"## Wikidata 字段\n{json.dumps(material['wikidata'], ensure_ascii=False, indent=2)}\n")
    if material.get("history"):
        page = material.get("history_page", "二十四史本传")
        parts.append(f"## 二十四史本传 ({page}, 简单清 markup 后 ~5000 字)\n{material['history']}\n")
    return "\n".join(parts)


def call_llm(model: str, system: str, user: str, temperature: float = 0.3,
             max_tokens: int = 4000, log: logging.Logger | None = None) -> dict:
    """调云雾 LLM, 返回 {content, usage, latency_s, model, finish_reason}.

    含 thinking model 防御: 若 reasoning_tokens > 0 且 content 空 → raise.
    """
    t0 = time.time()
    r = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=300,
    )
    latency = round(time.time() - t0, 2)
    r.raise_for_status()
    data = r.json()
    choice = data["choices"][0]
    content = choice["message"].get("content") or ""
    usage = data.get("usage", {})
    finish = choice.get("finish_reason")

    # thinking model 防御 (AC17)
    reasoning = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0) or 0
    if reasoning > 0 and not content.strip():
        raise RuntimeError(
            f"thinking model 检测: reasoning_tokens={reasoning} 但 content 空 "
            f"(model={model}). SPEC v1.0 禁用 thinking model, 请换 non-thinking 型号."
        )

    return {
        "model": model,
        "content": content,
        "usage": usage,
        "latency_s": latency,
        "finish_reason": finish,
    }


# 8 sections regex (validate profile 完整性)
PROFILE_SECTIONS_REQUIRED = [
    "基本信息", "主要事迹", "性格 / 风格特征", "典故 / 标志事件",
    "关键作品", "关系网", "历史评价", "反差 / 鲜为人知点",
]


def validate_profile_sections(profile_md: str) -> tuple[bool, list[str]]:
    """check profile 含 8 sections. 返回 (ok, missing_list)."""
    missing = []
    for sec in PROFILE_SECTIONS_REQUIRED:
        if not re.search(rf"^##\s+{re.escape(sec)}\s*$", profile_md, flags=re.MULTILINE):
            missing.append(sec)
    return len(missing) == 0, missing


def build_profile(name: str, material: dict, strong_model: str,
                  log: logging.Logger, max_retries: int = 1) -> tuple[str, dict]:
    """调强 LLM 产 profile.md. 含 thinking model 防御 + section 完整性 validation.

    返回 (profile_md, llm_call_info).
    """
    user_prompt = PROFILE_PROMPT.format(name=name) + "\n\n材料:\n" + material_to_text(material)
    last_err = None
    last_call = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            log.warning(f"  ↻ build_profile 重试 {attempt}/{max_retries}")
            time.sleep(2)
        try:
            res = call_llm(strong_model, "你是严谨的中国历史人物 profile 编辑。",
                           user_prompt, temperature=0.3, max_tokens=4000, log=log)
            last_call = res
            profile = res["content"].strip()
            # 去 markdown 包裹 (有些 LLM 会加)
            if profile.startswith("```"):
                profile = re.sub(r"^```(?:markdown|md)?\s*\n", "", profile)
                profile = re.sub(r"\n```\s*$", "", profile)
            ok, missing = validate_profile_sections(profile)
            if not ok:
                last_err = f"profile 缺 sections: {missing}"
                log.warning(f"  ⚠️ {last_err}")
                continue
            log.info(f"  ✓ profile {len(profile)} 字 ({res['latency_s']}s)")
            return profile, res
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:200]}"
            log.error(f"  ❌ build_profile 失败: {last_err}")
            if attempt == max_retries:
                raise
    raise RuntimeError(f"build_profile 重试 {max_retries + 1} 次后仍失败: {last_err}")


# ===== T10: clues_from_profile (banlist + few-shot inject) =====

CLUE_PROMPT = """你是中国历史人物题目编辑。给你 1 位历史人物的 profile + 一个 banlist (d1-5 必须避免的典故/作品名) + few-shot 好坏对比示例, 凝结 7 条难度梯度递增的猜谜线索。

输出 JSON schema (严格,无 ``` 包裹):
{{
  "name": "<画像 name>",
  "aliases": [<画像基本信息列出的字/号/谥号/庙号/别号, 5-8 个>],
  "clues": [
    {{"text": "<难度 1 — 最难, 30-60 字>", "difficulty": 1}},
    {{"text": "<难度 2>", "difficulty": 2}},
    {{"text": "<难度 3>", "difficulty": 3}},
    {{"text": "<难度 4>", "difficulty": 4}},
    {{"text": "<难度 5 — 标准范围最易>", "difficulty": 5}},
    {{"text": "<难度 6 — 求救范围>", "difficulty": 6}},
    {{"text": "<难度 7 — 求救范围, 几乎暴露>", "difficulty": 7}}
  ]
}}

难度规则:

**d1 (最难)** 必做:
- 只引用画像「反差 / 鲜为人知点」section 的 1-2 条内容
- 让普通人脱离朝代/作品/典故后, 只能凭隐晦反差去猜
**d1 禁做**:
- 含 banlist 任一词 (典故 / 关键作品)
- 含 aliases 任一字符 (整字 + 子串)
- 含朝代名 (汉/唐/宋/元/明/清/三国/秦/晋/隋 等)

**d2 (次难)**:
- 可触历史评价的最抽象描述
- 同 d1 禁做规则除朝代名外仍适用

**d3**:
- 可触关系网的抽象描述
- 同 d1 禁做规则除朝代名外仍适用

**d4-d5**:
- 可间接指代作品/典故 (不出 banlist 中具体名)
- 仍不含 aliases 字符

**d6 (求救范围)**:
- 可触朝代 / 作品名 / 典故 (banlist 词允许)
- 禁 aliases 整字 + 长度 ≥ 2 子串

**d7 (求救范围,几乎暴露)**:
- 同 d6,且禁 "字/号/谥号/庙号" 等关键字 + aliases 字符

通用:
- 每条 clue 单句, 30-60 字, 第三人称

----- BANLIST (d1-5 必避免) -----
{banlist}

----- few-shot 反例 (这些是常见 d1 穿底, 勿模仿) -----
{bad_examples}

----- few-shot 正例 (你的输出该像这样) -----
{good_examples}

----- 人物 profile -----
{profile}

----- 上次违规反馈 (若有, 改进) -----
{retry_feedback}
"""


def load_few_shot_examples() -> tuple[list[str], list[str]]:
    """parse scripts/few_shot_examples.md → (good_examples, bad_examples) text list."""
    if not FEW_SHOT_POOL.exists():
        return [], []
    md = FEW_SHOT_POOL.read_text(encoding="utf-8")
    # 简化 parse: 抓 "### 坏 #N" 和 "### 好 #N" section
    bad, good = [], []
    sections = re.split(r"^### (好|坏) #\d+", md, flags=re.MULTILINE)
    # sections format: [prefix, "坏", content, "好", content, ...]
    for i in range(1, len(sections) - 1, 2):
        kind = sections[i]
        body = sections[i + 1].split("\n### ")[0].strip()
        if kind == "坏":
            bad.append(body[:400])  # 截短避免 prompt 太长
        else:
            good.append(body[:400])
    return good, bad


def parse_json_safe(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


def clues_from_profile(profile_md: str, banlist: list[str], good_examples: list[str],
                       bad_examples: list[str], flash_model: str, log: logging.Logger,
                       retry_feedback: str = "") -> tuple[dict, dict]:
    """flash LLM 产 7 条 clues.

    返回 (clues_obj, llm_call_info).
    """
    import random
    # 随机 1 好 1 坏 inject (避免 LLM overfit 同 1 对)
    good = random.choice(good_examples) if good_examples else "(few-shot pool 暂空)"
    bad = random.choice(bad_examples) if bad_examples else "(few-shot pool 暂空)"
    banlist_str = "\n".join(f"- {b}" for b in banlist) if banlist else "(无 banlist, 自由生成)"

    user_prompt = CLUE_PROMPT.format(
        banlist=banlist_str,
        bad_examples=bad,
        good_examples=good,
        profile=profile_md,
        retry_feedback=retry_feedback or "(无)",
    )
    res = call_llm(flash_model, "你是严谨的中国历史人物题目编辑, 严格 JSON 输出。",
                   user_prompt, temperature=0.3, max_tokens=2000, log=log)
    try:
        clues_obj = parse_json_safe(res["content"])
        if "clues" not in clues_obj or len(clues_obj["clues"]) != 7:
            raise ValueError(f"clues 数 ≠ 7: {clues_obj}")
        log.info(f"  ✓ {len(clues_obj['clues'])} 条 clues ({res['latency_s']}s)")
        return clues_obj, res
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        log.error(f"  ❌ clues parse 失败: {e}, raw 前 200: {res['content'][:200]}")
        raise


# ===== T11+T12: judge + auto retry loop =====

def judge_and_retry_loop(figure_name: str, profile_md: str, banlist: list[str],
                         good_examples: list[str], bad_examples: list[str],
                         flash_model: str, judge_model: str, max_judge_retries: int,
                         log: logging.Logger) -> tuple[dict | None, list[dict], str | None]:
    """Auto retry loop: clue 生成 → judge → 若违规 → inject 反馈 retry. 最多 N 次.

    返回 (final_clues_obj, all_llm_calls, failure_reason 或 None).
    failure_reason=None → 成功; 否则该 figure 标 failed.
    """
    all_calls = []
    retry_feedback = ""

    for attempt in range(max_judge_retries + 1):
        if attempt > 0:
            log.warning(f"  ↻ judge retry {attempt}/{max_judge_retries}")
            time.sleep(2)

        # Step: 生成 clues (含 retry_feedback)
        try:
            clues_obj, clue_call = clues_from_profile(
                profile_md, banlist, good_examples, bad_examples, flash_model, log,
                retry_feedback=retry_feedback,
            )
            all_calls.append(clue_call)
        except Exception as e:
            return None, all_calls, f"clues_from_profile 失败: {e}"

        # Step: judge
        try:
            judge_result = judge_clues_llm(
                figure={"aliases": clues_obj.get("aliases", []), "clues": clues_obj.get("clues", [])},
                profile_md=profile_md,
                model=judge_model,
                llm_call_fn=lambda m, s, u: _llm_call_for_judge(m, s, u, log),
            )
        except Exception as e:
            log.warning(f"  ⚠️ judge 失败 (不阻塞): {e}")
            judge_result = {"verdicts": [], "judge_error": str(e)}

        # 检查 verdicts
        violations = [v for v in judge_result.get("verdicts", []) if v.get("verdict") == "违规"]
        if not violations:
            log.info(f"  ✓ judge 通过 ({len(judge_result.get('verdicts', []))} 条 clue 全合规/可疑)")
            return clues_obj, all_calls, None

        # 有违规 — 准备 retry feedback
        log.warning(f"  ⚠️ {len(violations)} 条违规, 准备 retry")
        retry_feedback = "上次生成的违规 clues (请避免类似问题):\n" + "\n".join(
            f"- d{v.get('d')}: {v.get('reason', '?')}" for v in violations
        )

    return None, all_calls, f"judge 重试 {max_judge_retries + 1} 次后仍违规"


def _llm_call_for_judge(model: str, system: str, user: str, log: logging.Logger) -> str:
    """judge_clues_llm 的 llm_call_fn adapter."""
    res = call_llm(model, system, user, temperature=0.1, max_tokens=2000, log=log)
    return res["content"]


# ===== T13: cost cap + cost_summary.json =====

def estimate_cost_cny(model: str, usage: dict) -> float:
    """估算单 LLM call 的人民币成本 (¥)."""
    prompt_t = usage.get("prompt_tokens", 0)
    completion_t = usage.get("completion_tokens", 0)
    rate_key = "default"
    m_lower = model.lower()
    if "deepseek" in m_lower:
        rate_key = "deepseek"
    elif "haiku" in m_lower or "claude" in m_lower:
        rate_key = "claude-haiku"
    elif "gemini" in m_lower:
        rate_key = "gemini"
    elif "gpt" in m_lower:
        rate_key = "gpt"
    rate = COST_RATE[rate_key]
    return prompt_t * rate["in"] + completion_t * rate["out"]


def update_cost_summary(figure_name: str, calls: list[dict]) -> dict:
    """累积 cost_summary.json, 返回更新后的 summary."""
    COST_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary = {"total_cost_cny": 0.0, "by_figure": {}}
    if COST_SUMMARY.exists():
        try:
            summary = json.loads(COST_SUMMARY.read_text(encoding="utf-8"))
        except Exception:
            pass
    figure_cost = 0.0
    figure_calls = []
    for c in calls:
        cost = estimate_cost_cny(c["model"], c.get("usage", {}))
        figure_cost += cost
        figure_calls.append({
            "model": c["model"],
            "usage": c.get("usage", {}),
            "cost_cny": round(cost, 4),
            "latency_s": c.get("latency_s"),
        })
    summary["by_figure"][figure_name] = {
        "total_cost_cny": round(figure_cost, 4),
        "calls": figure_calls,
    }
    summary["total_cost_cny"] = round(
        sum(f["total_cost_cny"] for f in summary["by_figure"].values()), 4
    )
    COST_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def append_failed(figure_name: str, reason: str):
    FAILED_FIGURES.parent.mkdir(parents=True, exist_ok=True)
    failed = []
    if FAILED_FIGURES.exists():
        try:
            failed = json.loads(FAILED_FIGURES.read_text(encoding="utf-8"))
        except Exception:
            pass
    failed.append({
        "name": figure_name,
        "reason": reason,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    FAILED_FIGURES.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")


# ===== 主流程 =====
def name_to_id(name: str) -> str:
    return name.strip().replace(" ", "-").lower()


def load_history_index() -> dict:
    if not HISTORY_INDEX.exists():
        return {}
    return json.loads(HISTORY_INDEX.read_text(encoding="utf-8"))


def process_one(name: str, strong_model: str, flash_model: str, judge_model: str,
                history_index: dict, good_examples: list[str], bad_examples: list[str],
                max_judge_retries: int, log: logging.Logger) -> dict | None:
    """单 figure 完整流程. 成功返回 figure dict; 失败 (重试穷尽) 返回 None + 写 failed."""
    log.info(f"━━━ 处理: {name} ━━━")
    all_calls = []
    try:
        # T7: fetch 三源
        history_mapping = history_index.get(name)
        material, qid = fetch_three_sources(name, history_mapping, log)
        if not material:
            append_failed(name, "维基中文无该人物条目")
            return None

        # T8: build profile
        profile, profile_call = build_profile(name, material, strong_model, log)
        all_calls.append(profile_call)
        # 写 profile 到 src/lib/data/profiles/
        fid = name_to_id(name)
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        (PROFILES_DIR / f"{fid}.md").write_text(profile, encoding="utf-8")

        # T9: extract banlist (reuse quality_check.py 实现)
        banlist = extract_banlist_from_profile(profile)
        log.debug(f"  banlist ({len(banlist)} 词): {banlist[:5]}...")

        # T10+T11+T12: clue + judge + retry loop
        clues_obj, judge_calls, fail_reason = judge_and_retry_loop(
            name, profile, banlist, good_examples, bad_examples,
            flash_model, judge_model, max_judge_retries, log,
        )
        all_calls.extend(judge_calls)

        if fail_reason:
            append_failed(name, fail_reason)
            update_cost_summary(name, all_calls)  # 即使 fail 也累积成本
            return None

        # 组装 V1 兼容 figure
        figure = {
            "name": clues_obj.get("name", name),
            "aliases": clues_obj.get("aliases", []),
            "clues": clues_obj.get("clues", []),
            "id": fid,
            "source": "wikipedia+wikidata+wikisource" if material.get("history") else "wikipedia+wikidata",
            "wikidata_id": qid,
            "wiki_url": f"https://zh.wikipedia.org/wiki/{name}",
            "wikisource_page": material.get("history_page"),
            "_meta": {
                "model_strong": strong_model,
                "model_flash": flash_model,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pipeline_version": "v2",
                "llm_calls": len(all_calls),
            },
        }

        summary = update_cost_summary(name, all_calls)
        log.info(f"  ✅ {name} 完成 (总成本 ¥{summary['by_figure'][name]['total_cost_cny']}, "
                 f"累计 ¥{summary['total_cost_cny']})")

        # T13: cost hard cap
        if summary["total_cost_cny"] > COST_HARD_CAP_CNY:
            log.error(f"❌ 总成本 ¥{summary['total_cost_cny']} > 硬上限 ¥{COST_HARD_CAP_CNY}, ABORT")
            sys.exit(3)

        return figure
    except Exception as e:
        last_err = f"{type(e).__name__}: {str(e)[:300]}"
        log.error(f"  ❌ process_one 失败: {last_err}")
        append_failed(name, last_err)
        update_cost_summary(name, all_calls)
        return None


def main():
    parser = argparse.ArgumentParser(
        description="内容生产 pipeline v2 (003)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="跑法见 docstring",
    )
    src_grp = parser.add_mutually_exclusive_group(required=True)
    src_grp.add_argument("--names", help="figure 名列表 (逗号分隔)")
    src_grp.add_argument("--names-from", help="从 JSON 文件 (如 src/lib/data/figures.json) 提取 names")

    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 JSON 路径")
    parser.add_argument("--strong-llm", default="deepseek-v3.2", help="强 LLM model (profile 用)")
    parser.add_argument("--flash-llm", default=FLASH_MODEL_DEFAULT, help="flash LLM model (clues 用)")
    parser.add_argument("--judge-llm", default=FLASH_MODEL_DEFAULT, help="judge LLM model")
    parser.add_argument("--max-judge-retries", type=int, default=2, help="judge 违规重试次数 N (默认 2)")
    args = parser.parse_args()

    if not LLM_API_KEY:
        raise SystemExit("❌ 缺 YUNWU_API_KEY")

    log = setup_logging()

    # 提取 names
    if args.names_from:
        figs = json.loads(Path(args.names_from).read_text(encoding="utf-8"))
        names = [f["name"] for f in figs]
    else:
        names = [n.strip() for n in args.names.split(",") if n.strip()]

    log.info(f"开始 v2 pipeline: {len(names)} figure")
    log.info(f"配置: strong={args.strong_llm}, flash={args.flash_llm}, judge={args.judge_llm}, retries={args.max_judge_retries}")

    history_index = load_history_index()
    log.info(f"history_index: {len(history_index)} entry")
    good_examples, bad_examples = load_few_shot_examples()
    log.info(f"few-shot pool: {len(good_examples)} 好 + {len(bad_examples)} 坏")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figures = []

    for i, name in enumerate(names, 1):
        log.info(f"\n[{i}/{len(names)}]")
        if i > 1:
            time.sleep(3)  # figure 间 cool down 避免 Wikidata 429
        fig = process_one(name, args.strong_llm, args.flash_llm, args.judge_llm,
                          history_index, good_examples, bad_examples,
                          args.max_judge_retries, log)
        if fig:
            figures.append(fig)
        # 增量保存
        output_path.write_text(json.dumps(figures, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info(f"\n{'=' * 60}")
    log.info(f"✅ 成功 {len(figures)}/{len(names)}")
    log.info(f"📄 输出: {output_path}")
    if FAILED_FIGURES.exists():
        failed = json.loads(FAILED_FIGURES.read_text(encoding="utf-8"))
        log.info(f"❌ failed: {len(failed)} (见 {FAILED_FIGURES})")
    if COST_SUMMARY.exists():
        summary = json.loads(COST_SUMMARY.read_text(encoding="utf-8"))
        log.info(f"💰 总成本: ¥{summary['total_cost_cny']}")
    log.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()
