from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import error as url_error
from urllib import request as url_request


DEFAULT_BUCKET = "guess-figure-turtle-corpus"
DEFAULT_VECTORIZE_INDEX = "guess-figure-turtle-rag"
DEFAULT_D1_DATABASE = "guess-figure-db"
DEFAULT_EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b"
DEFAULT_VECTOR_DIMENSIONS = 1024
DEFAULT_WRANGLER_ARGS = ("exec", "wrangler")


def default_wrangler_bin_for_platform(os_name: str = os.name) -> str:
    return "pnpm.cmd" if os_name == "nt" else "pnpm"


DEFAULT_WRANGLER_BIN = default_wrangler_bin_for_platform()


@dataclass(frozen=True)
class CloudflareIngestConfig:
    bucket: str = DEFAULT_BUCKET
    vectorize_index: str = DEFAULT_VECTORIZE_INDEX
    d1_database: str = DEFAULT_D1_DATABASE
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    vector_dimensions: int = DEFAULT_VECTOR_DIMENSIONS
    vector_metric: str = "cosine"
    mock_embedding: bool = False
    wrangler_bin: str = DEFAULT_WRANGLER_BIN
    wrangler_args: tuple[str, ...] = DEFAULT_WRANGLER_ARGS
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    embedding_batch_size: int = 64


class CommandFailure(RuntimeError):
    def __init__(self, command: list[str], message: str, returncode: int = 1):
        self.command = command
        self.returncode = returncode
        super().__init__(f"{message}: {' '.join(command)}")


CommandRunner = Callable[[list[str], Path | None], Any]
Embedder = Callable[[list[dict[str, Any]], CloudflareIngestConfig], list[list[float]]]


def default_command_runner(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "wrangler command failed").strip()
        raise CommandFailure(command, error, result.returncode)


def build_wrangler_command(config: CloudflareIngestConfig, args: list[str]) -> list[str]:
    return [config.wrangler_bin, *config.wrangler_args, *args]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def mock_embedding(chunk_id: str, text: str, dimensions: int) -> list[float]:
    """生成稳定的测试向量，避免单测和 sample 链路调用真实 Workers AI。"""
    seed = hashlib.sha256(f"{chunk_id}:{text}".encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimensions:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for byte in digest:
            values.append(round((byte / 127.5) - 1.0, 6))
            if len(values) == dimensions:
                break
        counter += 1
    return values


def workers_ai_embedder(rows: list[dict[str, Any]], config: CloudflareIngestConfig) -> list[list[float]]:
    """通过 Workers AI REST API 生成真实 embedding；测试可用 embedder 参数替换。"""
    account_id = config.cloudflare_account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = config.cloudflare_api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        raise CommandFailure(["workers-ai", "embed", config.embedding_model], "缺少 CLOUDFLARE_ACCOUNT_ID 或 CLOUDFLARE_API_TOKEN")

    payload = json.dumps({"text": [str(row["text"]) for row in rows]}, ensure_ascii=False).encode("utf-8")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{config.embedding_model}"
    body: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(5):
        request = url_request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with url_request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
                break
        except url_error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 4:
                raise CommandFailure(["workers-ai", "embed", config.embedding_model], detail, error.code) from error
            retry_after = error.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1)
            last_error = error
            time.sleep(wait)
        except (TimeoutError, url_error.URLError) as error:
            if attempt == 4:
                raise CommandFailure(["workers-ai", "embed", config.embedding_model], str(error)) from error
            last_error = error
            time.sleep(2.0 * (attempt + 1))
    if body is None:
        raise CommandFailure(["workers-ai", "embed", config.embedding_model], str(last_error or "Workers AI 请求失败"))

    result = body.get("result", {})
    data = result.get("data") if isinstance(result, dict) else None
    if not body.get("success", False) or not isinstance(data, list):
        raise CommandFailure(["workers-ai", "embed", config.embedding_model], json.dumps(body, ensure_ascii=False))
    return data


def build_embeddings(
    rows: list[dict[str, Any]],
    config: CloudflareIngestConfig,
    embedder: Embedder | None,
) -> list[list[float]]:
    if config.mock_embedding:
        return [
            mock_embedding(str(row["metadata"]["chunk_id"]), str(row["text"]), config.vector_dimensions)
            for row in rows
        ]

    vectors: list[list[float]] = []
    batch_size = max(1, config.embedding_batch_size)
    active_embedder = embedder or workers_ai_embedder
    for start in range(0, len(rows), batch_size):
        vectors.extend(active_embedder(rows[start : start + batch_size], config))
    if len(vectors) != len(rows):
        raise ValueError(f"embedding 数量不匹配：期望 {len(rows)}，实际 {len(vectors)}")
    for index, vector in enumerate(vectors):
        if len(vector) != config.vector_dimensions:
            raise ValueError(f"第 {index} 条 embedding 维度不是 {config.vector_dimensions}")
    return vectors


def normalize_source_text(parts: list[str]) -> str:
    return " ".join(" ".join(parts).split())


def collect_source_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        metadata = row["metadata"]
        key = (str(metadata.get("source_type", "")), str(metadata.get("source_id", "")))
        source = sources.setdefault(
            key,
            {
                "source_type": key[0],
                "source_id": key[1],
                "title": metadata.get("title"),
                "figure_id": metadata.get("figure_id"),
                "figure_name": metadata.get("figure_name"),
                "source_url": metadata.get("source_url"),
                "chunk_ids": [],
                "text_segments": [],
            },
        )
        source["chunk_ids"].append(metadata.get("chunk_id"))
        source["text_segments"].append(row["text"])

    records: list[dict[str, Any]] = []
    for source in sources.values():
        records.append(
            {
                **source,
                "chunk_count": len(source["chunk_ids"]),
                "char_count": sum(len(part) for part in source["text_segments"]),
            }
        )
    return sorted(records, key=lambda item: (item["source_type"], item["source_id"]))


def collect_affected_source_ranges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        metadata = row["metadata"]
        key = (str(metadata.get("source_type", "")), str(metadata.get("source_id", "")))
        source = sources.setdefault(
            key,
            {
                "source_type": key[0],
                "source_id": key[1],
                "title": metadata.get("title"),
                "figure_id": metadata.get("figure_id"),
                "figure_name": metadata.get("figure_name"),
                "chunks": [],
            },
        )
        source["chunks"].append(
            {
                "chunk_id": metadata.get("chunk_id"),
                "start": int(metadata.get("start", 0)),
                "end": int(metadata.get("end", 0)),
            }
        )

    affected: list[dict[str, Any]] = []
    for source in sources.values():
        affected.append({**source, "chunk_count": len(source["chunks"])})
    return sorted(affected, key=lambda item: (item["source_type"], item["source_id"]))


def write_source_artifacts(chunks_path: Path, output_dir: Path) -> dict[str, str]:
    rows = load_jsonl(chunks_path)
    records = collect_source_records(rows)
    raw_path = output_dir / "sources-raw.jsonl"
    normalized_path = output_dir / "sources-normalized.jsonl"

    with raw_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    with normalized_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            normalized = dict(record)
            normalized["normalized_text"] = normalize_source_text(record["text_segments"])
            normalized.pop("text_segments", None)
            file.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True) + "\n")

    return {
        "raw_sources_jsonl": str(raw_path),
        "normalized_sources_jsonl": str(normalized_path),
    }


def write_vectorize_upsert_file(
    chunks_path: Path,
    output_dir: Path,
    config: CloudflareIngestConfig,
    embedder: Embedder | None = None,
) -> Path:
    upsert_path = output_dir / "vectorize-upsert.jsonl"
    rows = load_jsonl(chunks_path)
    vectors = build_embeddings(rows, config, embedder)
    with upsert_path.open("w", encoding="utf-8", newline="\n") as file:
        for row, vector in zip(rows, vectors):
            metadata = dict(row["metadata"])
            chunk_id = str(metadata["chunk_id"])
            metadata["text"] = row["text"]
            metadata["embedding_model"] = config.embedding_model
            metadata["vector_dimensions"] = config.vector_dimensions
            metadata["vector_metric"] = config.vector_metric
            payload = {
                "id": chunk_id,
                "values": vector,
                "metadata": metadata,
            }
            file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return upsert_path


def sql_quote(value: Any) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def build_manifest_sql(report: dict[str, Any], r2_keys: dict[str, str], config: CloudflareIngestConfig) -> str:
    corpus_version = report["corpus_version"]
    index_version = report["index_version"]
    chunk_count = int(report["chunk_count"])
    failures = report.get("failures", [])
    failed_count = len(failures)
    source_counts = report.get("source_counts", {})
    source_total = sum(int(value) for value in source_counts.values())
    stats_json = json.dumps(
        {
            "source_counts": source_counts,
            "history_book_stats": report.get("history_book_stats", []),
            "budget": report.get("budget", {}),
            "r2_keys": r2_keys,
            "checkpoint": "cloud-checkpoint.json",
            "status": "succeeded",
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    source_records = report.get("source_records", [])
    source_sql = [build_source_record_sql(corpus_version, item) for item in source_records if isinstance(item, dict)]
    refresh_totals_sql = build_refresh_version_totals_sql(corpus_version, index_version)

    return "\n".join(
        [
            (
                "INSERT INTO turtle_corpus_versions "
                "(version, status, r2_prefix, manifest_r2_key, source_count, chunk_count, vector_count, "
                "failed_source_count, stats_json, completed_at, updated_at) VALUES "
                f"({sql_quote(corpus_version)}, 'ready', {sql_quote(r2_keys['prefix'])}, {sql_quote(r2_keys['build_report'])}, "
                f"{source_total}, {chunk_count}, {chunk_count}, {failed_count}, {sql_quote(stats_json)}, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT(version) DO UPDATE SET status='ready', manifest_r2_key=excluded.manifest_r2_key, "
                "source_count=excluded.source_count, chunk_count=excluded.chunk_count, vector_count=excluded.vector_count, "
                "failed_source_count=excluded.failed_source_count, stats_json=excluded.stats_json, "
                "completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP;"
            ),
            (
                "INSERT INTO turtle_index_versions "
                "(index_version, corpus_version, vectorize_index_name, embedding_model, vector_dimensions, "
                "vector_metric, status, chunk_count, vector_count, metadata_json, activated_at) VALUES "
                f"({sql_quote(index_version)}, {sql_quote(corpus_version)}, {sql_quote(config.vectorize_index)}, "
                f"{sql_quote(config.embedding_model)}, {config.vector_dimensions}, {sql_quote(config.vector_metric)}, "
                f"'active', {chunk_count}, {chunk_count}, {sql_quote(stats_json)}, CURRENT_TIMESTAMP) "
                "ON CONFLICT(index_version) DO UPDATE SET status='active', chunk_count=excluded.chunk_count, "
                "vector_count=excluded.vector_count, metadata_json=excluded.metadata_json, activated_at=CURRENT_TIMESTAMP;"
            ),
            (
                "INSERT INTO turtle_build_reports "
                "(corpus_version, index_version, status, report_r2_object_key, checkpoint_r2_object_key, "
                "source_total, source_processed, source_failed, chunk_count, vector_count, token_estimate, stats_json, completed_at) VALUES "
                f"({sql_quote(corpus_version)}, {sql_quote(index_version)}, 'succeeded', {sql_quote(r2_keys['build_report'])}, "
                f"{sql_quote(r2_keys['checkpoint'])}, {source_total}, {source_total - failed_count}, {failed_count}, "
                f"{chunk_count}, {chunk_count}, {int(report.get('budget', {}).get('token_budget_used', 0) or 0)}, "
                f"{sql_quote(stats_json)}, CURRENT_TIMESTAMP);"
            ),
            *source_sql,
            refresh_totals_sql,
        ]
    )


def build_source_record_sql(corpus_version: str, record: dict[str, Any]) -> str:
    status = str(record.get("status") or "processed")
    if status not in {"pending", "processed", "failed", "skipped"}:
        status = "failed"
    return (
        "INSERT INTO turtle_corpus_sources "
        "(corpus_version, source_type, source_id, figure_id, title, source_url, source_ref, "
        "checksum_sha256, status, char_count, byte_count, chunk_count, error_message, updated_at) VALUES "
        f"({sql_quote(corpus_version)}, {sql_quote(record.get('source_type'))}, {sql_quote(record.get('source_id'))}, "
        f"{sql_quote(record.get('figure_id'))}, {sql_quote(record.get('title'))}, {sql_quote(record.get('source_url'))}, "
        f"{sql_quote(record.get('source_ref'))}, NULL, {sql_quote(status)}, "
        f"{int(record.get('char_count') or 0)}, 0, {int(record.get('chunk_count') or 0)}, "
        f"{sql_quote(record.get('error_message'))}, CURRENT_TIMESTAMP) "
        "ON CONFLICT(corpus_version, source_type, source_id) DO UPDATE SET "
        "figure_id=excluded.figure_id, title=excluded.title, source_url=excluded.source_url, "
        "source_ref=excluded.source_ref, status=excluded.status, char_count=excluded.char_count, "
        "byte_count=excluded.byte_count, chunk_count=excluded.chunk_count, error_message=excluded.error_message, "
        "updated_at=CURRENT_TIMESTAMP;"
    )


def build_refresh_version_totals_sql(corpus_version: str, index_version: str) -> str:
    quoted_corpus = sql_quote(corpus_version)
    quoted_index = sql_quote(index_version)
    return "\n".join(
        [
            (
                "UPDATE turtle_corpus_versions SET "
                f"source_count=(SELECT COUNT(*) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus}), "
                f"chunk_count=(SELECT COALESCE(SUM(chunk_count), 0) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus}), "
                f"vector_count=(SELECT COALESCE(SUM(chunk_count), 0) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus}), "
                f"failed_source_count=(SELECT COUNT(*) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus} AND status='failed'), "
                "updated_at=CURRENT_TIMESTAMP "
                f"WHERE version={quoted_corpus};"
            ),
            (
                "UPDATE turtle_index_versions SET "
                f"chunk_count=(SELECT COALESCE(SUM(chunk_count), 0) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus}), "
                f"vector_count=(SELECT COALESCE(SUM(chunk_count), 0) FROM turtle_corpus_sources WHERE corpus_version={quoted_corpus}) "
                f"WHERE index_version={quoted_index};"
            ),
        ]
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_failure_artifacts(
    output_dir: Path,
    report: dict[str, Any],
    completed_steps: list[str],
    failed_step: str,
    error: Exception,
    r2_keys: dict[str, str],
) -> None:
    chunks_path = output_dir / "chunks.jsonl"
    affected_sources: list[dict[str, Any]] = []
    affected_chunk_count = 0
    if chunks_path.exists():
        rows = load_jsonl(chunks_path)
        affected_chunk_count = len(rows)
        affected_sources = collect_affected_source_ranges(rows)
    checkpoint = {
        "completed_steps": completed_steps,
        "failed_step": failed_step,
        "error": str(error),
        "affected_sources": affected_sources,
        "affected_chunk_count": affected_chunk_count,
        "resume_args": build_resume_args(report, output_dir),
        "resume_note": "当前 checkpoint 记录进度和失败点；恢复方式是从头重跑同一命令，已完成步骤不会被自动跳过。",
        "r2_keys": r2_keys,
        "report_keys": report.get("output_files", {}),
        "source_counts": report.get("source_counts", {}),
    }
    failed_sources = {
        "failed_step": failed_step,
        "error": str(error),
        "source_counts": report.get("source_counts", {}),
        "failures": report.get("failures", []),
        "affected_sources": affected_sources,
        "affected_chunk_count": affected_chunk_count,
    }
    write_json(output_dir / "cloud-checkpoint.json", checkpoint)
    write_json(output_dir / "failed-sources.json", failed_sources)


def build_resume_args(report: dict[str, Any], output_dir: Path) -> list[str]:
    build_args = report.get("build_args", {})
    mode = str(build_args.get("mode") or "sample") if isinstance(build_args, dict) else "sample"
    args = ["python", "scripts/build_turtle_corpus.py"]
    if mode == "full-history":
        args.append("--full-history")
    else:
        args.append("--sample")
    args.extend(["--cloud", "--output", str(output_dir)])
    if not isinstance(build_args, dict):
        return args
    if build_args.get("mock_embedding"):
        args.append("--mock-embedding")
    if mode == "full-history":
        option_map = [
            ("daily_token_budget", "--daily-token-budget"),
            ("daily_vector_limit", "--daily-vector-limit"),
            ("max_books", "--max-books"),
            ("max_pages_per_book", "--max-pages-per-book"),
            ("resume_after", "--resume-after"),
            ("batch_id", "--batch-id"),
            ("discovery_sleep", "--discovery-sleep"),
            ("embedding_batch_size", "--embedding-batch-size"),
        ]
        for key, flag in option_map:
            value = build_args.get(key)
            if value is not None:
                args.extend([flag, str(value)])
        if build_args.get("skip_local_sources"):
            args.append("--skip-local-sources")
    elif build_args.get("sample_size") is not None:
        args.extend(["--sample-size", str(build_args["sample_size"])])
    return args


def build_r2_keys(report: dict[str, Any]) -> dict[str, str]:
    prefix = str(report.get("r2_prefix") or f"{report['corpus_version']}/")
    if not prefix.endswith("/"):
        prefix += "/"
    return {
        "prefix": prefix,
        "build_report": f"{prefix}build-report.json",
        "chunks_jsonl": f"{prefix}chunks.jsonl",
        "raw_sources_jsonl": f"{prefix}sources-raw.jsonl",
        "normalized_sources_jsonl": f"{prefix}sources-normalized.jsonl",
        "checkpoint": f"{prefix}cloud-checkpoint.json",
    }


def ingest_corpus_to_cloudflare(
    report: dict[str, Any],
    output_dir: Path,
    config: CloudflareIngestConfig,
    command_runner: CommandRunner = default_command_runner,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    output_dir = output_dir.resolve(strict=False)
    report_path = output_dir / "build-report.json"
    chunks_path = output_dir / "chunks.jsonl"
    r2_keys = build_r2_keys(report)
    completed_steps: list[str] = []

    try:
        if not config.mock_embedding and embedder is None:
            account_id = config.cloudflare_account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
            api_token = config.cloudflare_api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
            if not account_id or not api_token:
                raise CommandFailure(
                    ["workers-ai", "embed", config.embedding_model],
                    "缺少 CLOUDFLARE_ACCOUNT_ID 或 CLOUDFLARE_API_TOKEN，未开始写入 R2/Vectorize/D1",
                )
        source_files = write_source_artifacts(chunks_path, output_dir)
        command_runner(
            build_wrangler_command(
                config,
                ["r2", "object", "put", f"{config.bucket}/{r2_keys['build_report']}", "--file", str(report_path)],
            ),
            None,
        )
        command_runner(
            build_wrangler_command(
                config,
                ["r2", "object", "put", f"{config.bucket}/{r2_keys['chunks_jsonl']}", "--file", str(chunks_path)],
            ),
            None,
        )
        command_runner(
            build_wrangler_command(
                config,
                [
                    "r2",
                    "object",
                    "put",
                    f"{config.bucket}/{r2_keys['raw_sources_jsonl']}",
                    "--file",
                    source_files["raw_sources_jsonl"],
                ],
            ),
            None,
        )
        command_runner(
            build_wrangler_command(
                config,
                [
                    "r2",
                    "object",
                    "put",
                    f"{config.bucket}/{r2_keys['normalized_sources_jsonl']}",
                    "--file",
                    source_files["normalized_sources_jsonl"],
                ],
            ),
            None,
        )
        completed_steps.append("r2_upload")

        upsert_path = write_vectorize_upsert_file(chunks_path, output_dir, config, embedder=embedder)
        command_runner(
            build_wrangler_command(config, ["vectorize", "upsert", config.vectorize_index, "--file", str(upsert_path)]),
            None,
        )
        completed_steps.append("vectorize_upsert")

        sql = build_manifest_sql(report, r2_keys, config)
        sql_path = output_dir / "cloud-manifest.sql"
        sql_path.write_text(sql + "\n", encoding="utf-8")
        command_runner(
            build_wrangler_command(
                config,
                ["d1", "execute", config.d1_database, "--remote", "--file", str(sql_path)],
            ),
            None,
        )
        completed_steps.append("d1_manifest")
    except Exception as error:
        failed_step = "d1_manifest"
        if completed_steps == []:
            failed_step = "r2_upload"
        elif completed_steps == ["r2_upload"]:
            failed_step = "vectorize_upsert"
        write_failure_artifacts(output_dir, report, completed_steps, failed_step, error, r2_keys)
        raise

    summary = {
        "status": "succeeded",
        "completed_steps": completed_steps,
        "r2_keys": r2_keys,
        "vectorize_file": str(output_dir / "vectorize-upsert.jsonl"),
        "manifest_sql": str(output_dir / "cloud-manifest.sql"),
        "source_files": source_files,
        "vector_dimensions": config.vector_dimensions,
        "embedding_model": config.embedding_model,
    }
    write_json(output_dir / "cloud-checkpoint.json", summary)
    return summary
