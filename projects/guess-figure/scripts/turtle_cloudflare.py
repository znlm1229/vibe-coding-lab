from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_BUCKET = "guess-figure-turtle-corpus"
DEFAULT_VECTORIZE_INDEX = "guess-figure-turtle-rag"
DEFAULT_D1_DATABASE = "guess-figure-db"
DEFAULT_EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b"
DEFAULT_VECTOR_DIMENSIONS = 1024
DEFAULT_WRANGLER_BIN = "pnpm exec wrangler"


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


class CommandFailure(RuntimeError):
    def __init__(self, command: list[str], message: str, returncode: int = 1):
        self.command = command
        self.returncode = returncode
        super().__init__(f"{message}: {' '.join(command)}")


CommandRunner = Callable[[list[str], Path | None], Any]


def default_command_runner(command: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "wrangler command failed").strip()
        raise CommandFailure(command, error, result.returncode)


def build_wrangler_command(config: CloudflareIngestConfig, args: list[str]) -> list[str]:
    return config.wrangler_bin.split() + args


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


def write_vectorize_upsert_file(
    chunks_path: Path,
    output_dir: Path,
    config: CloudflareIngestConfig,
) -> Path:
    if not config.mock_embedding:
        raise ValueError("当前入库脚本只支持 --mock-embedding；真实 Workers AI embedding 留给可 mock 封装后接入")

    upsert_path = output_dir / "vectorize-upsert.jsonl"
    rows = load_jsonl(chunks_path)
    with upsert_path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            metadata = dict(row["metadata"])
            chunk_id = str(metadata["chunk_id"])
            metadata["text"] = row["text"]
            metadata["embedding_model"] = config.embedding_model
            metadata["vector_dimensions"] = config.vector_dimensions
            metadata["vector_metric"] = config.vector_metric
            payload = {
                "id": chunk_id,
                "values": mock_embedding(chunk_id, row["text"], config.vector_dimensions),
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
            "r2_keys": r2_keys,
            "checkpoint": "cloud-checkpoint.json",
            "status": "succeeded",
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    return "\n".join(
        [
            "BEGIN;",
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
                "source_total, source_processed, source_failed, chunk_count, vector_count, stats_json, completed_at) VALUES "
                f"({sql_quote(corpus_version)}, {sql_quote(index_version)}, 'succeeded', {sql_quote(r2_keys['build_report'])}, "
                f"{sql_quote(r2_keys['checkpoint'])}, {source_total}, {source_total - failed_count}, {failed_count}, "
                f"{chunk_count}, {chunk_count}, {sql_quote(stats_json)}, CURRENT_TIMESTAMP);"
            ),
            "COMMIT;",
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
    checkpoint = {
        "completed_steps": completed_steps,
        "failed_step": failed_step,
        "error": str(error),
        "resume_command": f"python scripts/build_turtle_corpus.py --sample --cloud --output {output_dir} --mock-embedding",
        "r2_keys": r2_keys,
        "report_keys": report.get("output_files", {}),
        "source_counts": report.get("source_counts", {}),
    }
    failed_sources = {
        "failed_step": failed_step,
        "error": str(error),
        "source_counts": report.get("source_counts", {}),
        "failures": report.get("failures", []),
    }
    write_json(output_dir / "cloud-checkpoint.json", checkpoint)
    write_json(output_dir / "failed-sources.json", failed_sources)


def build_r2_keys(report: dict[str, Any]) -> dict[str, str]:
    prefix = f"{report['corpus_version']}/"
    return {
        "prefix": prefix,
        "build_report": f"{prefix}build-report.json",
        "chunks_jsonl": f"{prefix}chunks.jsonl",
        "checkpoint": f"{prefix}cloud-checkpoint.json",
    }


def ingest_corpus_to_cloudflare(
    report: dict[str, Any],
    output_dir: Path,
    config: CloudflareIngestConfig,
    command_runner: CommandRunner = default_command_runner,
) -> dict[str, Any]:
    output_dir = output_dir.resolve(strict=False)
    report_path = output_dir / "build-report.json"
    chunks_path = output_dir / "chunks.jsonl"
    r2_keys = build_r2_keys(report)
    completed_steps: list[str] = []

    try:
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
        completed_steps.append("r2_upload")

        upsert_path = write_vectorize_upsert_file(chunks_path, output_dir, config)
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
                ["d1", "execute", config.d1_database, "--remote", "--command", sql],
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
        "vector_dimensions": config.vector_dimensions,
        "embedding_model": config.embedding_model,
    }
    write_json(output_dir / "cloud-checkpoint.json", summary)
    return summary
