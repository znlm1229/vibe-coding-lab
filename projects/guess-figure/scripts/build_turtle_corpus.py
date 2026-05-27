#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from turtle_corpus import build_sample_corpus, load_figures, load_profiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURES_PATH = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
PROFILES_DIR = PROJECT_ROOT / "src" / "lib" / "data" / "profiles"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建海龟汤 RAG 本地语料小样本")
    parser.add_argument("--sample", action="store_true", help="只构建小样本 dry-run")
    parser.add_argument("--output", type=Path, required=True, help="输出目录，不默认写入仓库大文件目录")
    parser.add_argument("--sample-size", type=int, default=3, help="小样本人数量，默认 3")
    return parser.parse_args()


def is_output_inside_project(output_dir: Path) -> bool:
    output_path = output_dir.resolve(strict=False)
    project_path = PROJECT_ROOT.resolve(strict=False)
    try:
        output_path.relative_to(project_path)
    except ValueError:
        return False
    return True


def main() -> int:
    args = parse_args()
    if not args.sample:
        print("当前 T2 只支持 --sample dry-run；全量入库由 T3 处理。", file=sys.stderr)
        return 2
    if is_output_inside_project(args.output):
        print(
            f"拒绝写入仓库内 output 目录：{args.output}。请使用 $env:TEMP 或其他仓库外临时目录。",
            file=sys.stderr,
        )
        return 2

    figures = load_figures(FIGURES_PATH)
    figure_names = [str(item.get("name") or item.get("id") or "") for item in figures[: args.sample_size]]
    profiles = load_profiles(PROFILES_DIR, figure_names)
    result = build_sample_corpus(args.output, figures, profiles, sample_size=args.sample_size)

    print(json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result.report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
