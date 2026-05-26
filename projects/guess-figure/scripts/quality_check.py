#!/usr/bin/env python3
"""
题库自动质量校验脚本（T4）。

6 项检查 (003 v3 升级, T3 加第 6 项):
1. aliases 数 3-5
2. clues 数 = 7
3. 难度 1-7 各 1 个齐全
4. 难度 1-5 全段不含任何 aliases (字符整字)
5. 难度 1 不含朝代名
6. 难度 6-7 不含 aliases 子串 (长度 ≥ 2; T3 新增)

跑法:
  python scripts/quality_check.py src/lib/data/figures.json
  python scripts/quality_check.py figures-new.json --strict   # 任一不合规 exit 1（CI 友好）
  python scripts/quality_check.py figures.json --verbose      # 显示每条 clue 文字

退出码:
  0 = 全部通过
  1 = 文件错误（不存在 / 非 JSON / 非数组）
  2 = 有 figure 不合规 + --strict
"""

import argparse
import json
import sys
from pathlib import Path

# 朝代关键词。区分"朝代名"vs"时期副词"：
# - 朝代名（视为违规）：明确的政权名称
# - 时期副词（不违规）：如"春秋时期"/"战国时期"作为时间形容词的用法
# - 故意排除单字（"夏"/"商"/"周"/"明"/"清" 等）避免 prototype A 的 false positive：
#   "发明家"含"明"、"商人"含"商"、"周末"含"周"
DYNASTY_KEYWORDS = [
    # 主要朝代（含"朝"后缀，最严谨）
    "秦朝", "汉朝", "西汉", "东汉",
    "晋朝", "西晋", "东晋",
    "隋朝", "唐朝",
    "宋朝", "北宋", "南宋",
    "元朝", "明朝", "清朝",
    # 三国时代
    "三国", "蜀汉", "曹魏", "孙吴",
    # 五代 / 南北朝
    "五代", "五代十国", "南北朝",
    # 民国 / PRC
    "民国", "中华民国", "中华人民共和国",
    # 注意：故意不包含 "春秋"、"战国"、"夏"、"商"、"周"、"明"、"清" 等单字
    # —— "春秋时期"作时间副词不算暴露朝代归属
    # —— 单字易误命中："发明""周末""商人""清晨"
]


# 2-字通用职衔/类目词 — alias 子串若命中这些不算 flag (避免 "皇帝"/"丞相"/"将军" 等泛指词的 false positive)
ALIAS_SUBSTRING_STOPWORDS = {
    # 帝王类
    "皇帝", "皇后", "太子", "太皇", "太上", "皇上",
    # 职官
    "丞相", "宰相", "宰执", "尚书", "侍郎", "御史", "中书", "中令", "詹事",
    "将军", "都督", "节度", "刺史", "县令", "县尉", "县丞",
    "大夫", "大臣", "大将", "学士", "校尉",
    "夫人", "公主", "诸侯", "贵妃", "皇妃",
    # 泛指
    "万世", "千秋", "百代", "天下", "古今",
}


def _alias_substrings(alias: str, min_len: int = 2) -> list[str]:
    """生成 alias 的所有 ≥ min_len 长度的子串。

    例: "关云长" → ["关云", "云长", "关云长"]; min_len=2 时单字"关""云""长"被排除。
    """
    subs = []
    n = len(alias)
    if n < min_len:
        return subs
    for L in range(min_len, n + 1):
        for i in range(n - L + 1):
            subs.append(alias[i:i + L])
    return subs


def _is_alias_substring_violating(sub: str) -> bool:
    """alias 子串是否算违规 — 通用职衔/类目词不算 (e.g. '皇帝' 子串 ⊂ '昭烈皇帝' 不 flag)"""
    if len(sub) < 2:
        return False
    if sub in ALIAS_SUBSTRING_STOPWORDS:
        return False
    return True


def check_figure(f: dict) -> tuple[int, list[str]]:
    """返回 (score 0-6, warnings list)。

    6 项 check:
    1. aliases 数 3-5
    2. clues 数 = 7
    3. 难度 1-7 各 1 个齐全
    4. 难度 1-5 不含任何 aliases 整字
    5. 难度 1 不含朝代名
    6. 难度 6-7 不含 aliases 子串 (T3, 长度 ≥ 2)
    """
    score = 0
    warnings = []

    aliases = f.get("aliases") or []
    clues = f.get("clues") or []

    # 1. aliases 数 3-5
    if 3 <= len(aliases) <= 5:
        score += 1
    else:
        warnings.append(f"aliases 数 {len(aliases)} 不在 [3, 5]")

    # 2. clues 数 7
    if len(clues) == 7:
        score += 1
    else:
        warnings.append(f"clues 数 {len(clues)} ≠ 7")

    # 3. difficulty 1-7 齐
    diffs = sorted([c.get("difficulty") for c in clues if isinstance(c, dict)])
    if diffs == [1, 2, 3, 4, 5, 6, 7]:
        score += 1
    else:
        warnings.append(f"难度分布 {diffs} ≠ [1-7]")

    # 4. 难度 1-5 不含任何 aliases 字眼（关键约束）
    if aliases and clues:
        leak = None
        for c in clues:
            if isinstance(c, dict) and c.get("difficulty", 0) <= 5:
                text = c.get("text", "")
                for a in aliases:
                    if a and a in text:
                        leak = (c.get("difficulty"), a)
                        break
                if leak:
                    break
        if not leak:
            score += 1
        else:
            warnings.append(f"难度 {leak[0]} 含异称 '{leak[1]}'")

    # 5. 难度 1 不含朝代名（精确匹配，避免 prototype A 的 false positive）
    d1 = next((c for c in clues if isinstance(c, dict) and c.get("difficulty") == 1), None)
    if d1:
        text = d1.get("text", "")
        bad = [w for w in DYNASTY_KEYWORDS if w in text]
        if not bad:
            score += 1
        else:
            warnings.append(f"难度 1 含朝代名 {bad}")

    # 6. 难度 6-7 不含 aliases 子串 (T3, 长度 ≥ 2; 单字不查避免 "关" / "关于" false positive)
    if aliases and clues:
        leak = None
        for c in clues:
            if not isinstance(c, dict):
                continue
            d = c.get("difficulty", 0)
            if d not in (6, 7):
                continue
            text = c.get("text", "")
            for a in aliases:
                if not a or len(a) < 2:
                    continue
                for sub in _alias_substrings(a, min_len=2):
                    if not _is_alias_substring_violating(sub):
                        continue  # 通用职衔/类目词跳过
                    if sub in text:
                        leak = (d, a, sub)
                        break
                if leak:
                    break
            if leak:
                break
        if not leak:
            score += 1
        else:
            warnings.append(f"难度 {leak[0]} 含 alias '{leak[1]}' 子串 '{leak[2]}'")

    return score, warnings


def main():
    parser = argparse.ArgumentParser(
        description="题库质量自动校验（5 项检查）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("figures_file", help="figures JSON 路径")
    parser.add_argument("--strict", action="store_true",
                        help="任一不合规则 exit 2（CI 友好）")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="同时打印每条 clue 文字（便于人工 spot check）")
    args = parser.parse_args()

    path = Path(args.figures_file)
    if not path.exists():
        print(f"❌ 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        figures = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(figures, list):
        print("❌ 必须是 JSON 数组", file=sys.stderr)
        sys.exit(1)

    print(f"📥 校验 {len(figures)} 个 figures（{path}）\n")

    perfect = 0
    issues_count = 0
    issues_total = 0

    for i, f in enumerate(figures, 1):
        name = f.get("name", "?")
        score, warnings = check_figure(f)
        status = "✅" if score == 6 else ("⚠️" if score >= 4 else "❌")
        print(f"{status} [{i:2}] {name:<10}  {score}/6")
        if warnings:
            for w in warnings:
                print(f"      ⚠️ {w}")
            issues_count += 1
            issues_total += len(warnings)
        else:
            perfect += 1

        if args.verbose:
            for c in f.get("clues") or []:
                if isinstance(c, dict):
                    print(f"      D{c.get('difficulty')}: {c.get('text', '')}")
            print()

    print(f"\n{'=' * 60}")
    print(f"✅ 满分: {perfect}/{len(figures)}")
    if issues_count:
        print(f"⚠️ 有 issue: {issues_count}/{len(figures)} 个 figures、{issues_total} 处 warning")
    else:
        print(f"🎉 全部通过！")
    print(f"{'=' * 60}")

    if args.strict and issues_count > 0:
        print(f"\n❌ --strict 模式 + {issues_count} 个 figure 有 issue", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
