from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_turtle_intro import (
    DEFAULT_FIGURES_PATH,
    DEFAULT_INTROS_PATH,
    load_json,
    validate_turtle_intros,
)


PLACEHOLDER_STEMS = (
    "薄雾未散",
    "空阶微响",
    "半盏微光",
    "旧帘微动",
    "冷雨初停",
    "白纸留痕",
    "暗纹浮起",
    "微尘暂落",
    "低声回转",
    "空白未合",
)


def make_placeholder(index: int) -> str:
    return PLACEHOLDER_STEMS[index % len(PLACEHOLDER_STEMS)]


def generate_missing_intros(figures: list[dict[str, Any]], intros: dict[str, Any]) -> dict[str, str]:
    result = {str(key): str(value) for key, value in intros.items()}
    for index, figure in enumerate(figures):
        figure_id = str(figure.get("id", ""))
        if figure_id and figure_id not in result:
            result[figure_id] = make_placeholder(index)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="生成缺失海龟汤汤面的保守占位草案")
    parser.add_argument("--figures", type=Path, default=DEFAULT_FIGURES_PATH)
    parser.add_argument("--intros", type=Path, default=DEFAULT_INTROS_PATH)
    parser.add_argument("--write", action="store_true", help="写回 intros 文件；默认只打印草案")
    args = parser.parse_args()

    figures = load_json(args.figures)
    intros = load_json(args.intros) if args.intros.exists() else {}
    generated = generate_missing_intros(figures, intros)
    errors = validate_turtle_intros(figures, generated)
    print(json.dumps(generated, ensure_ascii=False, indent=2))

    if errors:
        print("生成草案仍有校验问题：")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.write:
        args.intros.write_text(json.dumps(generated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已写入 {args.intros}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
