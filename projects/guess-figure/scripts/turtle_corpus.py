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
    source_ref: str | None = None
    book: str | None = None
    volume: str | None = None
    extra_metadata: dict[str, Any] | None = None


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

    # 末尾不足一个标准窗口时，回退起点生成合规尾窗，保证全文位置不丢失。
    last_end = chunks[-1].end
    if last_end < len(clean_text):
        desired_start = max(0, last_end - overlap)
        latest_valid_start = max(0, len(clean_text) - MIN_CHUNK_CHARS)
        tail_start = min(desired_start, latest_valid_start)
        tail_end = len(clean_text)
        if tail_end - tail_start > MAX_CHUNK_CHARS:
            tail_start = max(0, tail_end - chunk_size)
        tail = TextChunk(text=clean_text[tail_start:tail_end], start=tail_start, end=tail_end)
        if all((item.start, item.end) != (tail.start, tail.end) for item in chunks):
            chunks.append(tail)

    return sorted(chunks, key=lambda item: (item.start, item.end))


def metadata_size_bytes(metadata: dict[str, Any]) -> int:
    return len(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def estimate_embedding_tokens(text: str) -> int:
    """保守估算中文 embedding 输入 token；用于批处理预算，不替代真实计费。"""
    return max(1, len(normalize_text(text)))


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
        if source.source_ref:
            metadata["source_ref"] = source.source_ref
        if source.book:
            metadata["book"] = source.book
        if source.volume:
            metadata["volume"] = source.volume
        if source.extra_metadata:
            metadata.update(source.extra_metadata)
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
    selected = figures[:sample_size]
    sources: list[CorpusSource] = []
    for figure in selected:
        figure_name = str(figure.get("name") or figure.get("id") or "")
        sources.extend(build_local_sources(figure, profiles.get(figure_name)))

    return build_corpus_from_sources(output_dir=output_dir, sources=sources)


def empty_history_book_stats(history_book_names: list[str]) -> dict[str, dict[str, Any]]:
    return {
        book: {
            "book": book,
            "source_total": 0,
            "source_processed": 0,
            "source_failed": 0,
            "source_skipped": 0,
            "processed": 0,
            "failed": 0,
            "skipped": 0,
            "chunk_count": 0,
            "char_count": 0,
        }
        for book in history_book_names
    }


def update_history_stat(stats: dict[str, dict[str, Any]], book: str | None, field: str, amount: int = 1) -> None:
    if not book:
        return
    stat = stats.setdefault(book, empty_history_book_stats([book])[book])
    stat[field] += amount
    if field == "source_processed":
        stat["processed"] += amount
    elif field == "source_failed":
        stat["failed"] += amount
    elif field == "source_skipped":
        stat["skipped"] += amount


def build_corpus_from_sources(
    output_dir: Path,
    sources: list[CorpusSource],
    failures: list[dict[str, Any]] | None = None,
    history_book_names: list[str] | None = None,
    budget_report: dict[str, Any] | None = None,
    corpus_version: str = CORPUS_VERSION,
    index_version: str = INDEX_VERSION,
    r2_prefix: str | None = None,
) -> CorpusBuildResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_chunks: list[CorpusChunk] = []
    source_counts: dict[str, int] = {"profile": 0, "wikipedia": 0, "wikisource": 0}
    normalized_failures: list[dict[str, Any]] = [dict(item) for item in (failures or [])]
    source_records: list[dict[str, Any]] = []
    history_stats = empty_history_book_stats(history_book_names or [])

    for source in sources:
        source_counts[source.source_type] = source_counts.get(source.source_type, 0) + 1
        source_chunks = build_chunks_for_source(source)
        source_failed = False
        for chunk in source_chunks:
            metadata_bytes = metadata_size_bytes(chunk.metadata)
            if metadata_bytes >= MAX_METADATA_BYTES:
                source_failed = True
                normalized_failures.append(
                    {
                        "source_type": source.source_type,
                        "source_id": source.source_id,
                        "title": source.title,
                        "book": source.book,
                        "volume": source.volume,
                        "reason": "metadata_over_10k",
                        "metadata_bytes": metadata_bytes,
                    }
                )
        all_chunks.extend(source_chunks)
        status = "failed" if source_failed else "processed"
        source_records.append(
            {
                "source_type": source.source_type,
                "source_id": source.source_id,
                "title": source.title,
                "source_url": source.source_url,
                "source_ref": source.source_ref,
                "figure_id": source.figure_id,
                "figure_name": source.figure_name,
                "book": source.book,
                "volume": source.volume,
                "status": status,
                "chunk_count": len(source_chunks),
                "char_count": len(normalize_text(source.text)),
            }
        )
        if source.source_type == "wikisource" and source.book:
            update_history_stat(history_stats, source.book, "source_total")
            update_history_stat(history_stats, source.book, "source_processed")
            history_stats[source.book]["chunk_count"] += len(source_chunks)
            history_stats[source.book]["char_count"] += len(normalize_text(source.text))

    for failure in normalized_failures:
        source_type = str(failure.get("source_type") or "")
        if source_type:
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
        source_records.append(
            {
                "source_type": source_type,
                "source_id": failure.get("source_id"),
                "title": failure.get("title"),
                "source_url": failure.get("source_url"),
                "source_ref": failure.get("source_ref"),
                "book": failure.get("book"),
                "volume": failure.get("volume"),
                "status": failure.get("status", "failed"),
                "chunk_count": 0,
                "char_count": 0,
                "error_message": failure.get("error") or failure.get("reason"),
            }
        )
        if source_type == "wikisource":
            book = str(failure.get("book") or "")
            if book:
                update_history_stat(history_stats, book, "source_total")
                status = str(failure.get("status", "failed"))
                if status == "skipped":
                    update_history_stat(history_stats, book, "source_skipped")
                else:
                    update_history_stat(history_stats, book, "source_failed")

    report = {
        "corpus_version": corpus_version,
        "index_version": index_version,
        "r2_prefix": r2_prefix or f"{corpus_version}/",
        "chunk_policy": {
            "min_chars": MIN_CHUNK_CHARS,
            "max_chars": MAX_CHUNK_CHARS,
            "target_chars": DEFAULT_CHUNK_SIZE,
            "overlap_chars": DEFAULT_OVERLAP,
        },
        "source_counts": source_counts,
        "chunk_count": len(all_chunks),
        "failures": normalized_failures,
        "source_records": source_records,
        "output_files": {},
    }
    if history_stats:
        report["history_book_stats"] = sorted(history_stats.values(), key=lambda item: item["book"])
    if budget_report:
        report["budget"] = budget_report
        if budget_report.get("batch_id"):
            report["batch_id"] = budget_report["batch_id"]
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
