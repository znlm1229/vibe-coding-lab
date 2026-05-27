#!/usr/bin/env python3
"""
004 Stage 3 throwaway spike:
- 读取现有 profile 与少量 Wikisource 本传，验证 chunk / retrieval / rerank / 三态 prompt 的形状。
- 不写正式 src 代码，不创建 Cloudflare 资源。
- embedding 用 1024 维 deterministic mock，保持与 Workers AI qwen3-embedding-0.6b 的维度契约一致。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROTO_ROOT = Path(__file__).resolve().parent
FIGURES_PATH = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
PROFILES_DIR = PROJECT_ROOT / "src" / "lib" / "data" / "profiles"
HISTORY_INDEX_PATH = PROJECT_ROOT / "scripts" / "data" / "history_index.json"
ENV_PATH = PROJECT_ROOT / ".env"

DIMENSIONS = 1024
CHUNK_MIN = 500
CHUNK_MAX = 800
CHUNK_OVERLAP = 100
TOP_K_VECTOR = 20
TOP_K_FINAL = 6

TARGETS = ["诸葛亮", "关羽", "苏轼"]


@dataclass
class Chunk:
    id: str
    figure_id: str
    source_type: str
    source_ref: str
    offset: int
    text: str
    vector: list[float]


TEST_CASES = [
    {"figure": "诸葛亮", "question": "他是不是蜀汉丞相？", "expected": "是"},
    {"figure": "诸葛亮", "question": "他是否写过出师表？", "expected": "是"},
    {"figure": "诸葛亮", "question": "他是不是唐朝诗人？", "expected": "否"},
    {"figure": "诸葛亮", "question": "他跟刘备有关吗？", "expected": "是"},
    {"figure": "诸葛亮", "question": "他是谁？", "expected": "invalid"},
    {"figure": "关羽", "question": "他是不是被后世尊为武圣？", "expected": "是"},
    {"figure": "关羽", "question": "他是否跟刘备有关？", "expected": "是"},
    {"figure": "关羽", "question": "他是不是宋朝文人？", "expected": "否"},
    {"figure": "关羽", "question": "他有没有在荆州失守相关事件中失败？", "expected": "是"},
    {"figure": "关羽", "question": "介绍他的作品", "expected": "invalid"},
    {"figure": "苏轼", "question": "他是不是宋代文人？", "expected": "是"},
    {"figure": "苏轼", "question": "他是否写过赤壁赋？", "expected": "是"},
    {"figure": "苏轼", "question": "他是不是蜀汉丞相？", "expected": "否"},
    {"figure": "苏轼", "question": "他跟王安石变法有关吗？", "expected": "是"},
    {"figure": "苏轼", "question": "他有哪些作品？", "expected": "invalid"},
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def http_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "guess-figure-rag-spike/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 30) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def clean_wikitext(text: str) -> str:
    # 轻量清洗，只为 spike 验证；正式构建需要更完整的 wikitext parser。
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"={2,}\s*([^=]+?)\s*={2,}", r"\n\1\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_wikisource(page_name: str) -> str:
    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": page_name,
            "format": "json",
            "prop": "wikitext",
            "redirects": "true",
        }
    )
    data = http_json(f"https://zh.wikisource.org/w/api.php?{query}")
    raw = data.get("parse", {}).get("wikitext", {}).get("*", "")
    return clean_wikitext(raw)


def split_chunks(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？；;])", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) <= CHUNK_MAX:
            current += sentence
            continue
        if len(current) >= CHUNK_MIN:
            chunks.append(current)
            current = current[-CHUNK_OVERLAP:] + sentence
        else:
            chunks.append((current + sentence)[:CHUNK_MAX])
            current = (current + sentence)[CHUNK_MAX - CHUNK_OVERLAP :]
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) >= 80]


def hash_embedding(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    # 1024 维 hashing trick，只验证链路形状，不代表真实 embedding 质量。
    values = [0.0] * dimensions
    normalized = re.sub(r"\s+", "", text)
    grams = [normalized[i : i + 3] for i in range(max(1, len(normalized) - 2))]
    for gram in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        values[idx] += sign
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def char_bigrams(text: str) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    return {compact[i : i + 2] for i in range(max(0, len(compact) - 1))}


def rerank_score(query: str, chunk_text: str, vector_score: float) -> float:
    q = char_bigrams(query)
    c = char_bigrams(chunk_text)
    overlap = len(q & c) / max(1, len(q))
    return vector_score * 0.7 + overlap * 0.3


def is_yes_no_question(question: str) -> tuple[bool, str | None]:
    q = question.strip()
    invalid_patterns = [
        r"他是谁",
        r"是谁",
        r"叫什么",
        r"哪些",
        r"有什么",
        r"有哪些",
        r"介绍",
        r"列出",
        r"为什么",
        r"怎么",
        r"多少",
    ]
    if any(re.search(p, q) for p in invalid_patterns):
        return False, "请用可以回答是/否/无关的问题来提问"
    yes_no_markers = ["吗", "么", "是不是", "是否", "有没有", "有无", "能否", "可否", "有关"]
    if any(marker in q for marker in yes_no_markers):
        return True, None
    return False, "请用可以回答是/否/无关的问题来提问"


def build_corpus() -> tuple[list[Chunk], dict[str, Any]]:
    figures = {f["id"]: f for f in load_json(FIGURES_PATH)}
    history_index = load_json(HISTORY_INDEX_PATH)
    chunks: list[Chunk] = []
    manifest: dict[str, Any] = {"targets": [], "chunk_policy": {
        "min_chars": CHUNK_MIN,
        "max_chars": CHUNK_MAX,
        "overlap_chars": CHUNK_OVERLAP,
    }}

    for name in TARGETS:
        figure = figures[name]
        sources: list[tuple[str, str, str]] = []
        profile_path = PROFILES_DIR / f"{name}.md"
        sources.append(("profile", str(profile_path.relative_to(PROJECT_ROOT)), profile_path.read_text(encoding="utf-8")))

        history_meta = history_index.get(name, {})
        page_name = history_meta.get("wikisource_page")
        if page_name:
            try:
                history_text = fetch_wikisource(page_name)
                sources.append(("wikisource", page_name, history_text[:6000]))
            except Exception as exc:  # noqa: BLE001
                sources.append(("wikisource_error", page_name, f"FETCH_ERROR: {exc}"))

        target_record = {"figure": name, "aliases": figure.get("aliases", []), "sources": []}
        for source_type, source_ref, text in sources:
            raw_chunks = split_chunks(text)
            target_record["sources"].append(
                {"type": source_type, "ref": source_ref, "chars": len(text), "chunks": len(raw_chunks)}
            )
            for offset, chunk_text in enumerate(raw_chunks):
                raw_id = f"{name}:{source_type}:{source_ref}:{offset}:{chunk_text[:20]}"
                chunk_id = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        figure_id=name,
                        source_type=source_type,
                        source_ref=source_ref,
                        offset=offset,
                        text=chunk_text,
                        vector=hash_embedding(f"{name} {source_ref} {chunk_text}"),
                    )
                )
        manifest["targets"].append(target_record)
    return chunks, manifest


def retrieve(chunks: list[Chunk], figure: dict[str, Any], question: str) -> list[dict[str, Any]]:
    query_text = f"目标人物：{figure['name']}。别名：{'、'.join(figure.get('aliases', []))}。问题：{question}"
    query_vector = hash_embedding(query_text)
    vector_hits = sorted(
        ((chunk, cosine(query_vector, chunk.vector)) for chunk in chunks),
        key=lambda item: item[1],
        reverse=True,
    )[:TOP_K_VECTOR]
    reranked = sorted(
        (
            {
                "id": chunk.id,
                "figure_id": chunk.figure_id,
                "source_type": chunk.source_type,
                "source_ref": chunk.source_ref,
                "offset": chunk.offset,
                "vector_score": round(vector_score, 4),
                "rerank_score": round(rerank_score(query_text, chunk.text, vector_score), 4),
                "text": chunk.text,
            }
            for chunk, vector_score in vector_hits
        ),
        key=lambda item: item["rerank_score"],
        reverse=True,
    )
    return reranked[:TOP_K_FINAL]


def build_prompt(figure: dict[str, Any], question: str, evidence: list[dict[str, Any]]) -> str:
    evidence_text = "\n\n".join(
        f"[{i + 1}] id={item['id']} source={item['source_type']}:{item['source_ref']}\n{item['text'][:900]}"
        for i, item in enumerate(evidence)
    )
    return f"""你是猜历史人物游戏的海龟汤裁判。

目标人物：{figure['name']}
目标人物别名：{'、'.join(figure.get('aliases', []))}
用户问题：{question}

只允许根据下面证据回答：
{evidence_text}

规则：
- 如果证据支持用户问题为真，answer 输出「是」。
- 如果证据明确反驳用户问题，answer 输出「否」。
- 如果证据不足、问题过宽、问题与目标人物无清晰关系、或你不确定，answer 输出「无关」。
- 不要把没有召回到证据当作「否」。
- 输出严格 JSON，不要 markdown：
{{"answer":"是|否|无关","reason":"内部调试理由，不展示给玩家","evidence_ids":["chunk id"]}}
"""


def parse_jsonish(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1].removeprefix("json").strip()
    if not content.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            content = match.group(0)
    return json.loads(content)


def call_llm(prompt: str, env_values: dict[str, str]) -> dict[str, Any]:
    api_key = env_values.get("YUNWU_API_KEY") or os.environ.get("YUNWU_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 YUNWU_API_KEY，无法运行 live LLM")
    base_url = (env_values.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
    model = env_values.get("LLM_MODEL") or "gemini-3.1-flash-lite"
    url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    data = post_json(
        url,
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 300,
        },
        {"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = parse_jsonish(content)
    return {
        "model": model,
        "raw": content,
        "answer": parsed.get("answer"),
        "reason": parsed.get("reason", ""),
        "evidence_ids": parsed.get("evidence_ids", []),
    }


def heuristic_answer(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    # 无 live LLM 时仅返回无关，避免用写死答案伪造成功率。
    return {
        "model": "heuristic-no-llm",
        "raw": "",
        "answer": "无关",
        "reason": "未启用 live LLM；只验证检索链路，不判断事实",
        "evidence_ids": [item["id"] for item in evidence[:2]],
    }


def write_report(run_dir: Path, manifest: dict[str, Any], cases: list[dict[str, Any]], cloudflare: dict[str, Any]) -> None:
    total = len(cases)
    passed = sum(1 for case in cases if case["passed"])
    lines = [
        "# 004 Turtle Soup RAG Prototype Report",
        "",
        f"- 运行时间：{time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"- 结果：{passed}/{total} cases passed",
        f"- embedding：1024 维 deterministic mock（用于验证 Vectorize 维度契约，不代表真实语义质量）",
        f"- chunk：{CHUNK_MIN}-{CHUNK_MAX} 中文字，overlap {CHUNK_OVERLAP}",
        "",
        "## Cloudflare 预检",
        "",
        f"- Workers AI 模型存在：{cloudflare['workers_ai_models_found']}",
        f"- Vectorize index：{cloudflare['vectorize_state']}",
        f"- R2 状态：{cloudflare['r2_state']}",
        f"- D1 状态：{cloudflare['d1_state']}",
        "",
        "## Corpus",
        "",
        "```json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Cases",
        "",
        "| # | figure | question | expected | actual | pass | top evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for idx, case in enumerate(cases, start=1):
        evidence = case.get("evidence", [])
        # invalid 问法不会进入 RAG，因此没有证据；报告层显式标 n/a。
        top = evidence[0] if evidence else {}
        top_desc = (
            f"{top.get('source_type', '')}:{top.get('source_ref', '')}#{top.get('offset', '')}"
            if top
            else "n/a"
        )
        lines.append(
            f"| {idx} | {case['figure']} | {case['question']} | {case['expected']} | "
            f"{case['actual']} | {'PASS' if case['passed'] else 'FAIL'} | {top_desc} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- RAG 查询必须把目标人物姓名/别名作为隐藏 query expansion 注入，否则用户问题中的「他」无法稳定召回。",
            "- 全量语料链路需要 R2 启用和 Vectorize index 创建；当前账号可访问 Vectorize/Workers AI，但尚未创建 index，R2 尚未启用。",
            "- mock embedding 只能验证接口形状；Stage 4 SPEC 应要求 Stage 7 用真实 Workers AI embedding + Vectorize 做集成测试。",
        ]
    )
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-llm", action="store_true", help="使用 .env 中的云雾 LLM 跑三态裁判")
    parser.add_argument("--cloudflare-json", type=Path, help="Wrangler 预检结果 JSON")
    args = parser.parse_args()

    figures = {f["id"]: f for f in load_json(FIGURES_PATH)}
    chunks, manifest = build_corpus()
    env_values = load_env(ENV_PATH)

    cases: list[dict[str, Any]] = []
    for item in TEST_CASES:
        ok, message = is_yes_no_question(item["question"])
        if not ok:
            actual = "invalid"
            cases.append(
                {
                    **item,
                    "actual": actual,
                    "passed": actual == item["expected"],
                    "message": message,
                    "evidence": [],
                    "llm": None,
                }
            )
            continue

        figure = figures[item["figure"]]
        evidence = retrieve(chunks, figure, item["question"])
        if args.live_llm:
            try:
                llm_result = call_llm(build_prompt(figure, item["question"], evidence), env_values)
            except Exception as exc:  # noqa: BLE001
                llm_result = {"model": "live-llm-error", "answer": "无关", "reason": str(exc), "evidence_ids": []}
        else:
            llm_result = heuristic_answer(evidence)
        actual = str(llm_result.get("answer", "无关"))
        cases.append(
            {
                **item,
                "actual": actual,
                "passed": actual == item["expected"],
                "evidence": evidence,
                "llm": llm_result,
            }
        )

    run_dir = PROTO_ROOT / f"run-{time.strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cloudflare = {
        "workers_ai_models_found": "已通过 wrangler ai models --json 验证 qwen3-embedding/bge-m3/reranker 存在",
        "vectorize_state": "账号可访问 Vectorize，但尚未创建 index",
        "r2_state": "R2 尚未启用，wrangler r2 bucket list 返回 code 10042",
        "d1_state": "guess-figure-db 已存在",
    }

    (run_dir / "corpus_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(run_dir, manifest, cases, cloudflare)

    passed = sum(1 for case in cases if case["passed"])
    print(f"run_dir={run_dir}")
    print(f"cases={passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
