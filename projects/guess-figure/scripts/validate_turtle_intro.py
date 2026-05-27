from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FIGURES_PATH = ROOT_DIR / "src" / "lib" / "data" / "figures.json"
DEFAULT_INTROS_PATH = ROOT_DIR / "src" / "lib" / "data" / "turtle-intros.json"
MIN_INTRO_CHARS = 4
MAX_INTRO_CHARS = 8

# review 点名的强指向意象，容易让汤面回到人物生平、作品或典故。
REVIEW_FLAGGED_TERMS = ("梦", "歌", "碗", "烟", "棋", "黄", "挑灯", "篱", "铁屋")

# 只放强识别词：朝代、职业/身份、作品、亲属、常见地名与典故关键词。
BANLIST = (
    "夏朝",
    "商朝",
    "周朝",
    "春秋",
    "战国",
    "秦朝",
    "汉朝",
    "三国",
    "晋朝",
    "南北朝",
    "隋朝",
    "唐朝",
    "宋朝",
    "元朝",
    "明朝",
    "清朝",
    "皇帝",
    "皇后",
    "君主",
    "将军",
    "宰相",
    "丞相",
    "大臣",
    "诗人",
    "词人",
    "书法",
    "画家",
    "思想家",
    "政治家",
    "军事家",
    "文学家",
    "革命",
    "医生",
    "僧人",
    "皇子",
    "父亲",
    "母亲",
    "儿子",
    "女儿",
    "兄弟",
    "妻子",
    "祖父",
    "祖母",
    "孔庙",
    "长安",
    "洛阳",
    "江南",
    "北京",
    "南京",
    "杭州",
    "绍兴",
    "赤壁",
    "乌江",
    "汨罗",
    "梁山",
    "四库全书",
    "论语",
    "史记",
    "离骚",
    "资治通鉴",
    "三国演义",
    "桃园",
    "草船",
    "空城",
    "三顾",
    "岳母",
    "满江红",
    "水调歌头",
    "将进酒",
    "兰亭",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_intro(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(value.split())


def validate_turtle_intros(figures: list[dict[str, Any]], intros: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    figure_ids = [str(figure.get("id", "")) for figure in figures if figure.get("id")]
    figure_id_set = set(figure_ids)

    for figure_id in figure_ids:
        if figure_id not in intros:
            errors.append(f"{figure_id}: 缺少汤面")

    for intro_id in sorted(set(intros) - figure_id_set):
        errors.append(f"{intro_id}: 汤面没有对应人物")

    for figure in figures:
        figure_id = str(figure.get("id", ""))
        if not figure_id or figure_id not in intros:
            continue

        intro = normalize_intro(intros[figure_id])
        if not intro:
            errors.append(f"{figure_id}: 汤面必须是非空字符串")
            continue

        if len(intro) < MIN_INTRO_CHARS or len(intro) > MAX_INTRO_CHARS:
            errors.append(f"{figure_id}: 汤面长度必须为 {MIN_INTRO_CHARS}-{MAX_INTRO_CHARS} 字")

        name = str(figure.get("name", "")).strip()
        if name and name in intro:
            errors.append(f"{figure_id}: 汤面泄露姓名 {name}")

        for alias in figure.get("aliases") or []:
            alias_text = str(alias).strip()
            if len(alias_text) >= 2 and alias_text in intro:
                errors.append(f"{figure_id}: 汤面泄露别名 {alias_text}")

        for banned in BANLIST:
            if banned in intro:
                errors.append(f"{figure_id}: 汤面包含禁词 {banned}")

        for flagged in REVIEW_FLAGGED_TERMS:
            if flagged in intro:
                errors.append(f"{figure_id}: 汤面包含强意象 {flagged}")

    return errors


def build_sample_report(figures: list[dict[str, Any]], intros: dict[str, Any], sample_size: int = 10) -> dict[str, Any]:
    samples = []
    for figure in figures[:sample_size]:
        figure_id = str(figure.get("id", ""))
        intro = normalize_intro(intros.get(figure_id, ""))
        samples.append({"id": figure_id, "intro": intro, "length": len(intro)})

    return {
        "figure_count": len(figures),
        "intro_count": len(intros),
        "sample_size": len(samples),
        "samples": samples,
        "checks": ["姓名", "别名", "朝代", "职业", "作品", "典故", "亲属", "地名", "强意象"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="校验海龟汤极短隐晦汤面数据")
    parser.add_argument("--figures", type=Path, default=DEFAULT_FIGURES_PATH)
    parser.add_argument("--intros", type=Path, default=DEFAULT_INTROS_PATH)
    parser.add_argument("--sample-size", type=int, default=10)
    args = parser.parse_args()

    figures = load_json(args.figures)
    intros = load_json(args.intros)
    errors = validate_turtle_intros(figures, intros)
    report = build_sample_report(figures, intros, args.sample_size)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if errors:
        print("校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("校验通过：汤面未直接暴露姓名、别名、朝代、职业、作品、典故、亲属、地名、强意象。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
