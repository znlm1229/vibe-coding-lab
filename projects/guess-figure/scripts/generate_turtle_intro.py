from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.validate_turtle_intro import (
    DEFAULT_FIGURES_PATH,
    DEFAULT_INTROS_PATH,
    load_json,
    validate_turtle_intros,
)


PLACEHOLDER_STEMS = (
    "无声回环",
    "薄雾停步",
    "旧灯微冷",
    "空杯未满",
    "迟来的风",
    "背光而立",
    "纸上微尘",
    "暗处回声",
    "半醒之门",
    "静夜留白",
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
