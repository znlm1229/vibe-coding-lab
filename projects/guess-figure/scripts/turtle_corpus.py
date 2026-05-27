from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CORPUS_VERSION = "turtle-corpus-v1"
INDEX_VERSION = "turtle-rag-index-v1"
DEFAULT_CHUNK_SIZE = 700
DEFAULT_OVERLAP = 100
MIN_CHUNK_CHARS = 500
MAX_CHUNK_CHARS = 800
MAX_METADATA_BYTES = 10 * 1024


@dataclass(frozen=True)
class TextChunk:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class CorpusSource:
    source_type: str
    source_id: str
    title: str
    text: str
    figure_id: str | None = None
    figure_name: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class CorpusChunk:
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CorpusBuildResult:
    output_dir: Path
    chunks: list[CorpusChunk]
    report: dict[str, Any]


def normalize_text(text: str) -> str:
    """把多余空白压平，避免 chunk 边界被格式噪声影响。"""
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[TextChunk]:
    if chunk_size < MIN_CHUNK_CHARS or chunk_size > MAX_CHUNK_CHARS:
        raise ValueError("chunk_size 必须在 500-800 字之间")
    if overlap < 80 or overlap > 120:
        raise ValueError("overlap 必须在 80-120 字之间")

    clean_text = normalize_text(text)
    if not clean_text:
        return []
    if len(clean_text) <= chunk_size:
        return [TextChunk(text=clean_text, start=0, end=len(clean_text))]

    chunks: list[TextChunk] = []
    step = chunk_size - overlap
    start = 0
    while start + chunk_size <= len(clean_text):
        end = start + chunk_size
        chunks.append(TextChunk(text=clean_text[start:end], start=start, end=end))
        start += step

    # 尾段不足 500 字时已被上一个 chunk 覆盖，避免生成不合规长文 chunk。
    if len(clean_text) - start >= MIN_CHUNK_CHARS:
        chunks.append(TextChunk(text=clean_text[start:], start=start, end=len(clean_text)))
    return chunks


def metadata_size_bytes(metadata: dict[str, Any]) -> int:
    return len(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def ensure_sample_text_length(text: str) -> str:
    """dry-run 使用本地小样本，短摘要重复补足到可校验的 chunk 长度。"""
    normalized = normalize_text(text)
    if len(normalized) >= MIN_CHUNK_CHARS:
        return normalized
    if not normalized:
        return ""
    parts: list[str] = []
    while len(" ".join(parts)) < MIN_CHUNK_CHARS:
        parts.append(normalized)
    return " ".join(parts)


def build_chunk_id(source: CorpusSource, start: int, end: int, text: str) -> str:
    raw = f"{CORPUS_VERSION}:{source.source_type}:{source.source_id}:{start}:{end}:{text[:64]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def build_chunks_for_source(source: CorpusSource) -> list[CorpusChunk]:
    chunks: list[CorpusChunk] = []
    for item in chunk_text(source.text):
        metadata: dict[str, Any] = {
            "chunk_id": build_chunk_id(source, item.start, item.end, item.text),
            "source_type": source.source_type,
            "source_id": source.source_id,
            "title": source.title,
            "start": item.start,
            "end": item.end,
        }
        if source.figure_id:
            metadata["figure_id"] = source.figure_id
        if source.figure_name:
            metadata["figure_name"] = source.figure_name
        if source.source_url:
            metadata["source_url"] = source.source_url
        chunks.append(CorpusChunk(text=item.text, metadata=metadata))
    return chunks


def load_figures(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_profiles(profiles_dir: Path, figure_names: list[str]) -> dict[str, str]:
    profiles: dict[str, str] = {}
    for name in figure_names:
        path = profiles_dir / f"{name}.md"
        if path.exists():
            profiles[name] = path.read_text(encoding="utf-8")
    return profiles


def build_local_sources(figure: dict[str, Any], profile_text: str | None) -> list[CorpusSource]:
    figure_id = str(figure.get("id") or figure.get("name") or "")
    figure_name = str(figure.get("name") or figure_id)
    aliases = "、".join(str(item) for item in figure.get("aliases", []))
    clue_text = " ".join(str(item.get("text", "")) for item in figure.get("clues", []) if isinstance(item, dict))
    wiki_url = figure.get("wiki_url")
    wikisource_page = figure.get("wikisource_page")

    sources: list[CorpusSource] = []
    if profile_text:
        sources.append(
            CorpusSource(
                source_type="profile",
                source_id=f"profiles/{figure_name}.md",
                title=f"{figure_name}人物档案",
                text=ensure_sample_text_length(profile_text),
                figure_id=figure_id,
                figure_name=figure_name,
            )
        )

    wikipedia_text = (
        f"{figure_name}，别名：{aliases}。本地 Wikipedia 小样本依据人物题库摘要构建，"
        f"用于验证 RAG chunk 形状和 metadata，不代表完整百科条目。{clue_text}"
    )
    sources.append(
        CorpusSource(
            source_type="wikipedia",
            source_id=str(wiki_url or figure_id),
            title=f"{figure_name} Wikipedia 小样本",
            text=ensure_sample_text_length(wikipedia_text),
            figure_id=figure_id,
            figure_name=figure_name,
            source_url=str(wiki_url) if wiki_url else None,
        )
    )

    if wikisource_page:
        wikisource_text = (
            f"{figure_name}，维基文库页：{wikisource_page}。本地 dry-run 只写入可追溯小样本，"
            f"全量原文由后续入库链路处理。相关人物线索：{clue_text}"
        )
        sources.append(
            CorpusSource(
                source_type="wikisource",
                source_id=str(wikisource_page),
                title=f"{figure_name} Wikisource 小样本",
                text=ensure_sample_text_length(wikisource_text),
                figure_id=figure_id,
                figure_name=figure_name,
                source_url=f"https://zh.wikisource.org/wiki/{wikisource_page}",
            )
        )
    return sources


def build_sample_corpus(
    output_dir: Path,
    figures: list[dict[str, Any]],
    profiles: dict[str, str],
    sample_size: int = 3,
) -> CorpusBuildResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = figures[:sample_size]
    all_chunks: list[CorpusChunk] = []
    source_counts = {"profile": 0, "wikipedia": 0, "wikisource": 0}
    failures: list[dict[str, Any]] = []

    for figure in selected:
        figure_name = str(figure.get("name") or figure.get("id") or "")
        sources = build_local_sources(figure, profiles.get(figure_name))
        for source in sources:
            if source.source_type in source_counts:
                source_counts[source.source_type] += 1
            source_chunks = build_chunks_for_source(source)
            for chunk in source_chunks:
                metadata_bytes = metadata_size_bytes(chunk.metadata)
                if metadata_bytes >= MAX_METADATA_BYTES:
                    failures.append(
                        {
                            "source_id": source.source_id,
                            "reason": "metadata_over_10k",
                            "metadata_bytes": metadata_bytes,
                        }
                    )
            all_chunks.extend(source_chunks)

    report = {
        "corpus_version": CORPUS_VERSION,
        "index_version": INDEX_VERSION,
        "chunk_policy": {
            "min_chars": MIN_CHUNK_CHARS,
            "max_chars": MAX_CHUNK_CHARS,
            "target_chars": DEFAULT_CHUNK_SIZE,
            "overlap_chars": DEFAULT_OVERLAP,
        },
        "source_counts": source_counts,
        "chunk_count": len(all_chunks),
        "failures": failures,
        "output_files": {},
    }
    result = CorpusBuildResult(output_dir=output_dir, chunks=all_chunks, report=report)
    write_corpus_outputs(result)
    return result


def write_corpus_outputs(result: CorpusBuildResult) -> tuple[Path, Path]:
    report_path = result.output_dir / "build-report.json"
    chunks_path = result.output_dir / "chunks.jsonl"

    with chunks_path.open("w", encoding="utf-8", newline="\n") as file:
        for chunk in result.chunks:
            row = {"text": chunk.text, "metadata": chunk.metadata}
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    report = dict(result.report)
    report["output_files"] = {
        "report_json": str(report_path),
        "chunks_jsonl": str(chunks_path),
    }
    result.report.clear()
    result.report.update(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_path, chunks_path
