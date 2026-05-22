#!/usr/bin/env python3
"""
内容生产 pipeline（生产版，T3）。

从 prototype A 的 proto_generate.py 提升：
- argparse 命令行参数（--names / --output / --max-retries / --model）
- LLM 调用失败重试（指数退避 2s/4s/8s）
- 增量保存（每个 figure 跑完立即写文件，整体挂掉不丢已成功的）
- 控制台 INFO + log 文件 DEBUG（scripts/logs/generate_YYYYMMDD_HHMMSS.log）
- skip 维基/Wikidata 无条目人物（不挂全部，记 failed 报告）
- figure 自动加 id / wiki_url / _meta（model + generated_at + usage）

跑法:
  python scripts/generate_figures.py --names "诸葛亮,李白"
  python scripts/generate_figures.py --names "白居易" --max-retries 3 --output figures-batch1.json
  python scripts/generate_figures.py --names "曹操" --model gpt-5.4-nano

输出: figures-new.json（默认）含一个 JSON 数组，每个元素是一个 figure dict
下一步: python scripts/merge.py figures-new.json
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

load_dotenv()

# ===== 配置 =====
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "figures-new.json"
LOG_DIR = Path(__file__).parent / "logs"
USER_AGENT = "guess-figure/0.1 (vibe-coding-lab; content-pipeline)"

LLM_API_KEY = os.environ.get("YUNWU_API_KEY")
LLM_BASE_URL = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"
LLM_MODEL_DEFAULT = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")

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


# ===== 维基 / Wikidata =====
def search_wikidata_qid(name: str) -> str | None:
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbsearchentities", "search": name, "language": "zh",
            "format": "json", "type": "item", "limit": 5,
        },
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("search", [])
    return results[0]["id"] if results else None


def fetch_wikidata_fields(qid: str) -> dict:
    r = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities", "ids": qid, "format": "json",
            "languages": "zh|en", "props": "labels|aliases|claims|descriptions",
        },
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


def fetch_material(name: str, log: logging.Logger):
    """返回 (material, qid)，任一缺失返回 (None, None)。"""
    page = WIKIPEDIA.page(name)
    if not page.exists():
        log.warning(f"  ⚠️ 维基中文无 '{name}' 条目")
        return None, None
    wiki_summary = page.summary[:1000]
    log.debug(f"  维基中文摘要 {len(wiki_summary)} 字")

    qid = search_wikidata_qid(name)
    if not qid:
        log.warning(f"  ⚠️ Wikidata 搜不到 '{name}'")
        return None, None
    log.debug(f"  Wikidata QID: {qid}")

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


# ===== LLM 调用（带重试）=====
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


def call_llm_with_retry(model: str, prompt: str, max_retries: int, log: logging.Logger) -> dict:
    """LLM 调用 + 指数退避重试。返回 {content, usage}。"""
    last_err = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait_s = 2 ** attempt
            log.warning(f"  ↻ 重试 {attempt}/{max_retries}（等 {wait_s}s）")
            time.sleep(wait_s)
        try:
            r = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 8000,
                },
                timeout=180,
            )
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                log.error(f"  ❌ {last_err}")
                continue
            data = r.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            finish_reason = choice.get("finish_reason")
            if not content:
                reasoning_len = len(choice["message"].get("reasoning_content") or "")
                last_err = f"content 空 (finish={finish_reason}, reasoning {reasoning_len} 字 - reasoning model?)"
                log.error(f"  ❌ {last_err}")
                continue
            if finish_reason == "length":
                # 被截断，JSON 必然不完整，重试拿完整版
                last_err = f"被 max_tokens 截断 (finish=length, content 长 {len(content)} 字)"
                log.error(f"  ❌ {last_err}")
                continue
            return {"content": content, "usage": data.get("usage", {})}
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:200]}"
            log.error(f"  ❌ {last_err}")
    raise RuntimeError(f"LLM 调用 {max_retries + 1} 次后仍失败: {last_err}")


def parse_figure_json(content: str) -> dict:
    """从 LLM 返回提取 figure JSON。4 层容错：剥 <think> / 剥 markdown 代码块 / 抠首个 {} 块 / json.loads。"""
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


# ===== 主流程 =====
def name_to_id(name: str) -> str:
    """中文名 → 文件友好 id。保留中文 + 去空格 + 小写。"""
    return name.strip().replace(" ", "-").lower()


def process_one(name: str, model: str, max_retries: int, log: logging.Logger):
    """单人物完整流程。返回 figure dict 或 None（skip）。"""
    log.info(f"━━━ 处理：{name} ━━━")

    material, qid = fetch_material(name, log)
    if not material:
        return None

    prompt = PROMPT_TEMPLATE.format(material=material, name=name)
    llm_result = call_llm_with_retry(model, prompt, max_retries, log)

    try:
        figure = parse_figure_json(llm_result["content"])
    except json.JSONDecodeError as e:
        log.error(f"  ❌ JSON 解析失败: {e}\n  raw content 前 500 字: {llm_result['content'][:500]}")
        raise

    # 补 V1 schema 必备字段
    figure["id"] = name_to_id(figure.get("name", name))
    figure["source"] = "wikipedia+wikidata"
    figure["wikidata_id"] = qid
    figure["wiki_url"] = f"https://zh.wikipedia.org/wiki/{name}"
    figure["_meta"] = {
        "model": model,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "usage": llm_result["usage"],
    }

    aliases = figure.get("aliases", [])
    clues = figure.get("clues", [])
    log.info(f"  ✅ {name} 完成（aliases {len(aliases)} 个，clues {len(clues)} 条）")
    return figure


def main():
    parser = argparse.ArgumentParser(
        description="LLM 内容生产 pipeline（T3 生产版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            '  python scripts/generate_figures.py --names "诸葛亮,李白"\n'
            '  python scripts/generate_figures.py --names "白居易" --max-retries 3\n'
            '  python scripts/generate_figures.py --names "曹操" --model gpt-5.4-nano\n'
        ),
    )
    parser.add_argument("--names", required=True, help="人物名列表，逗号分隔（如 '诸葛亮,李白'）")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"输出 JSON 路径（默认 {DEFAULT_OUTPUT.name}）")
    parser.add_argument("--max-retries", type=int, default=2,
                        help="LLM 调用失败重试次数（默认 2）")
    parser.add_argument("--model", default=LLM_MODEL_DEFAULT,
                        help=f"LLM 模型（默认 {LLM_MODEL_DEFAULT}）")
    args = parser.parse_args()

    if not LLM_API_KEY:
        raise SystemExit("❌ 缺 YUNWU_API_KEY 环境变量。检查 projects/guess-figure/.env")

    log = setup_logging()

    names = [n.strip() for n in args.names.split(",") if n.strip()]
    log.info(f"开始生产 {len(names)} 个人物: {names}")
    log.info(f"配置: model={args.model}, max-retries={args.max_retries}, output={args.output}")
    log.info(f"      base_url={LLM_BASE_URL}")

    output_path = Path(args.output)
    figures = []
    failed = []

    for i, name in enumerate(names, 1):
        log.info(f"\n[{i}/{len(names)}]")
        try:
            fig = process_one(name, args.model, args.max_retries, log)
            if fig:
                figures.append(fig)
            else:
                failed.append((name, "skip：维基/Wikidata 无条目"))
        except Exception as e:
            failed.append((name, str(e)))
            log.error(f"  ❌ {name} 失败: {e}")

        # 增量保存
        output_path.write_text(
            json.dumps(figures, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.debug(f"  📝 增量保存 {len(figures)}/{i} 个 figures 到 {output_path}")

    log.info(f"\n{'=' * 60}")
    log.info(f"✅ 完成: {len(figures)}/{len(names)} 成功")
    log.info(f"📄 输出: {output_path}")
    if failed:
        log.warning(f"❌ 失败 {len(failed)} 个:")
        for name, err in failed:
            log.warning(f"  - {name}: {err}")
    log.info(f"{'=' * 60}\n")
    log.info(f"💡 下一步合并到主题库: python scripts/merge.py {output_path}")


if __name__ == "__main__":
    main()
