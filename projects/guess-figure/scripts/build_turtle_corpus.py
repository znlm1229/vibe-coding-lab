#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from turtle_cloudflare import CloudflareIngestConfig, CommandFailure, ingest_corpus_to_cloudflare
from turtle_corpus import build_corpus_from_sources, build_local_sources, build_sample_corpus, load_figures, load_profiles
from turtle_history import (
    HISTORY_BOOKS,
    build_history_batch,
    discover_history_pages,
    fetch_wikisource_text,
    source_budget,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES_PATH = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
PROFILES_DIR = PROJECT_ROOT / "src" / "lib" / "data" / "profiles"
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建海龟汤 RAG 语料")
    parser.add_argument("--sample", action="store_true", help="只构建小样本 dry-run")
    parser.add_argument("--full-history", action="store_true", help="构建全量二十四史/清史稿分批语料")
    parser.add_argument("--cloud", action="store_true", help="把本次构建产物写入 Cloudflare R2/Vectorize/D1")
    parser.add_argument("--mock-embedding", action="store_true", help="使用确定性 1024 维 mock embedding")
    parser.add_argument("--embedding-batch-size", type=int, default=64, help="Workers AI embedding 每批文本条数")
    parser.add_argument("--wrangler-bin", default=None, help="wrangler 可执行文件路径，默认使用 pnpm exec wrangler")
    parser.add_argument("--output", type=Path, required=True, help="输出目录，不默认写入仓库大文件目录")
    parser.add_argument("--sample-size", type=int, default=3, help="小样本人物数量，默认 3")
    parser.add_argument("--daily-token-budget", type=int, default=600_000, help="本批 embedding token 估算上限")
    parser.add_argument("--daily-vector-limit", type=int, default=700, help="本批 upsert 向量条数上限")
    parser.add_argument("--max-books", type=int, default=None, help="调试/分批：最多发现前 N 部史书")
    parser.add_argument("--max-pages-per-book", type=int, default=None, help="调试/分批：每部史书最多抓取 N 页")
    parser.add_argument("--resume-after", default=None, help="从上一批 report 的 next_resume_after 之后继续")
    parser.add_argument("--batch-id", default=None, help="本批 ID；默认根据输出目录名生成")
    parser.add_argument("--discovery-sleep", type=float, default=0.2, help="每部书目录发现后的停顿秒数")
    parser.add_argument("--skip-local-sources", action="store_true", help="续跑时跳过 profiles / 本地 wikipedia 小样本")
    return parser.parse_args()


def is_output_inside_project(output_dir: Path) -> bool:
    output_path = output_dir.resolve(strict=False)
    project_path = PROJECT_ROOT.resolve(strict=False)
    try:
        output_path.relative_to(project_path)
    except ValueError:
        return False
    return True


def load_local_env(path: Path = LOCAL_ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_cloud_config(args: argparse.Namespace) -> CloudflareIngestConfig:
    embedding_batch_size = int(getattr(args, "embedding_batch_size", 64))
    if args.wrangler_bin:
        return CloudflareIngestConfig(
            mock_embedding=args.mock_embedding,
            wrangler_bin=args.wrangler_bin,
            wrangler_args=(),
            embedding_batch_size=embedding_batch_size,
        )
    return CloudflareIngestConfig(
        mock_embedding=args.mock_embedding,
        embedding_batch_size=embedding_batch_size,
    )


def build_args_report(args: argparse.Namespace) -> dict[str, object]:
    payload: dict[str, object] = {
        "mode": "full-history" if args.full_history else "sample",
        "cloud": bool(args.cloud),
        "mock_embedding": bool(args.mock_embedding),
        "embedding_batch_size": int(args.embedding_batch_size),
    }
    if args.sample:
        payload["sample_size"] = int(args.sample_size)
    else:
        payload.update(
            {
                "daily_token_budget": int(args.daily_token_budget),
                "daily_vector_limit": int(args.daily_vector_limit),
                "max_books": args.max_books,
                "max_pages_per_book": args.max_pages_per_book,
                "resume_after": args.resume_after,
                "batch_id": args.batch_id,
                "discovery_sleep": float(args.discovery_sleep),
                "skip_local_sources": bool(args.skip_local_sources),
            }
        )
    return payload


def write_report_json(report: dict) -> None:
    report_path = report.get("output_files", {}).get("report_json")
    if report_path:
        Path(report_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_full_history_corpus(args: argparse.Namespace):
    sources = []
    local_tokens = 0
    local_vectors = 0
    if not args.skip_local_sources:
        figures = load_figures(FIGURES_PATH)
        figure_names = [str(item.get("name") or item.get("id") or "") for item in figures]
        profiles = load_profiles(PROFILES_DIR, figure_names)
        for figure in figures:
            figure_name = str(figure.get("name") or figure.get("id") or "")
            sources.extend(build_local_sources(figure, profiles.get(figure_name)))
        for source in sources:
            budget = source_budget(source.text)
            local_tokens += budget["tokens"]
            local_vectors += budget["vectors"]
        if local_tokens > args.daily_token_budget or local_vectors > args.daily_vector_limit:
            raise ValueError(
                "本地 profile/wiki source 已超过本批预算；请调高 --daily-token-budget/--daily-vector-limit，"
                "或续跑时使用 --skip-local-sources。"
            )

    pages = discover_history_pages(
        HISTORY_BOOKS,
        max_books=args.max_books,
        max_pages_per_book=args.max_pages_per_book,
        sleep_seconds=args.discovery_sleep,
    )
    history_batch = build_history_batch(
        pages=pages,
        fetch_text=fetch_wikisource_text,
        token_budget=args.daily_token_budget - local_tokens,
        vector_budget=args.daily_vector_limit - local_vectors,
        resume_after=args.resume_after,
    )
    all_sources = [*sources, *history_batch.sources]
    batch_id = args.batch_id or args.output.name
    budget = {
        **history_batch.budget,
        "batch_id": batch_id,
        "history_book_count": len(HISTORY_BOOKS),
        "discovered_history_pages": len(pages),
        "local_token_budget_used": local_tokens,
        "local_vector_budget_used": local_vectors,
        "token_budget_limit": args.daily_token_budget,
        "token_budget_used": local_tokens + int(history_batch.budget["token_budget_used"]),
        "vector_budget_limit": args.daily_vector_limit,
        "vector_budget_used": local_vectors + int(history_batch.budget["vector_budget_used"]),
    }
    return build_corpus_from_sources(
        output_dir=args.output,
        sources=all_sources,
        failures=history_batch.failures,
        history_book_names=HISTORY_BOOKS,
        budget_report=budget,
        r2_prefix=f"turtle-corpus-v1/batches/{batch_id}/",
    )


def main() -> int:
    args = parse_args()
    load_local_env()
    if args.sample == args.full_history:
        print("请且只请指定 --sample 或 --full-history。", file=sys.stderr)
        return 2
    if is_output_inside_project(args.output):
        print(
            f"拒绝写入仓库内 output 目录：{args.output}。请使用 $env:TEMP 或其他仓库外临时目录。",
            file=sys.stderr,
        )
        return 2

    if args.sample:
        figures = load_figures(FIGURES_PATH)
        figure_names = [str(item.get("name") or item.get("id") or "") for item in figures[: args.sample_size]]
        profiles = load_profiles(PROFILES_DIR, figure_names)
        result = build_sample_corpus(args.output, figures, profiles, sample_size=args.sample_size)
    else:
        result = build_full_history_corpus(args)

    result.report["build_args"] = build_args_report(args)
    write_report_json(result.report)

    if args.cloud:
        try:
            cloud_summary = ingest_corpus_to_cloudflare(
                result.report,
                output_dir=args.output,
                config=build_cloud_config(args),
            )
            result.report["cloud"] = cloud_summary
            write_report_json(result.report)
        except CommandFailure as error:
            print(f"Cloudflare 入库失败，已写入 cloud-checkpoint.json: {error}", file=sys.stderr)
            return error.returncode

    print(json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result.report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
