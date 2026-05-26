#!/usr/bin/env python3
"""
题库自动质量校验脚本（T4）。

8 项检查 (003 v3 升级):
1. aliases 数 3-5
2. clues 数 = 7
3. 难度 1-7 各 1 个齐全
4. 难度 1-5 全段不含任何 aliases (字符整字)
5. 难度 1 不含朝代名
6. 难度 1-5 不含 aliases ≥ 3 字 子串 (T3 + T14 fix; 与 check #4 整字检测互补;d6/d7 求救允许)
7. 难度 1-5 不含 profile typology / 关键作品 banlist (T4 新增, 需 --profiles-dir)
8. 难度 1-5 信息密度启发式 (T5 新增, 具体名词数符合梯度)

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
import os
import re
import sys
from pathlib import Path

import requests  # T6: judge LLM call

# T6: 仅 --with-judge 时才需要 (避免顶层 import 失败)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


# T5: 信息密度启发式 — 难度越低,具体名词数应越少
# 阈值: 难度 d 允许的最大具体名词数 (d6/d7 不查,求救范围允许密度任意)
SPECIFIC_TERM_THRESHOLDS = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}

# 具体名词识别 regex
SPECIFIC_TERM_PATTERNS = [
    r"《[^》]+》",                                          # 书名号
    r"[一-鿿]{1,4}(?:年间|年代|世纪)",              # 时代
    r"\d{2,4}\s*年(?![代间])",                              # 年份 "207年"
    r"[一-鿿]{2,4}(?:之战|之役|之乱|之变|之盟|起义|事件)",  # 历史事件
]


def count_specific_terms(text: str) -> int:
    """统计文本中的具体名词数 (启发式: 书名/年份/事件/朝代)。"""
    if not text:
        return 0
    n = 0
    for pat in SPECIFIC_TERM_PATTERNS:
        n += len(re.findall(pat, text))
    n += sum(1 for w in DYNASTY_KEYWORDS if w in text)  # 朝代名
    return n


# T4: profile typology / 关键作品 section regex (OQ10)
PROFILE_BANLIST_SECTIONS = ["典故 / 标志事件", "关键作品", "典故", "标志事件"]


def extract_banlist_from_profile(profile_md: str) -> list[str]:
    """从 profile.md 抽「典故/标志事件」+「关键作品」section 词列表 (T4)。

    每个 section 是 markdown `## 标题\\n- ...\\n- ...`,提取每个 bullet 的关键词:
    - "三顾茅庐:刘备三次拜访..." → "三顾茅庐"
    - "草庐对(隆中对)" → "草庐对" (取 ( 前)
    - "鞠躬尽瘁,死而后已" → "鞠躬尽瘁" (取 , 前)
    - 否则取前 6 字
    """
    if not profile_md:
        return []
    bans: list[str] = []
    for header in PROFILE_BANLIST_SECTIONS:
        m = re.search(
            rf"^##\s+{re.escape(header)}\s*\n((?:[-*]\s*.+\n?)+)",
            profile_md,
            flags=re.MULTILINE,
        )
        if not m:
            continue
        block = m.group(1)
        for line in block.split("\n"):
            line = line.strip()
            if not line or not line.startswith(("-", "*")):
                continue
            line = line[1:].strip()
            # 去括号注释 "(隆中对)" / "（隆中对）"
            line = re.sub(r"[(（].*?[)）]", "", line)
            # 取所有分隔符的最前段 (冒号 / 中文逗号 / 句号)
            line = re.split(r"[:：,，.。;；]", line, maxsplit=1)[0]
            line = line.strip()
            if 2 <= len(line) <= 12 and line not in bans:
                bans.append(line)
    return bans


def check_figure(f: dict, profile_md: str | None = None) -> tuple[int, int, list[str]]:
    """返回 (score, max_score, warnings)。

    Checks:
    1. aliases 数 3-5
    2. clues 数 = 7
    3. 难度 1-7 各 1 个齐全
    4. 难度 1-5 不含任何 aliases 整字
    5. 难度 1 不含朝代名
    6. 难度 1-5 不含 aliases ≥ 3 字 子串 (T3 + T14 fix)
    7. 难度 1-5 不含 profile typology / 关键作品 section banlist 词 (T4, 仅当 profile_md 给定)
    8. 难度 1-5 信息密度梯度合理 (T5, 总是检测)

    profile_md=None → max_score=7 (跳过 check #7);profile_md=str → max_score=8。
    """
    score = 0
    max_score = 7  # 1-6 + 8 = 7 总是
    if profile_md is not None:
        max_score = 8  # +1 for check #7

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

    # 6. 难度 1-5 不含 aliases ≥ 3 字 子串 (T3 + T14 fix, 与 judge prompt 一致)
    # 注: d6/d7 求救范围 Q4 决议允许暴露 alias, check #6 仅查 d1-5 (与 check #4 d1-5 整字检测互补)
    # 旧 ≥ 2 字过严, "高宗"/"世宗" 等 2 字 alias 几乎不可避免; judge prompt 已放宽 ≥ 3 字
    if aliases and clues:
        leak = None
        for c in clues:
            if not isinstance(c, dict):
                continue
            d = c.get("difficulty", 0)
            if d not in (1, 2, 3, 4, 5):
                continue
            text = c.get("text", "")
            for a in aliases:
                if not a or len(a) < 3:
                    continue
                for sub in _alias_substrings(a, min_len=3):
                    if not _is_alias_substring_violating(sub):
                        continue
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
            warnings.append(f"难度 {leak[0]} 含 alias '{leak[1]}' ≥ 3 字子串 '{leak[2]}'")

    # 7. d1-5 不含 profile typology/关键作品 section banlist 词 (T4, 需要 profile_md)
    if profile_md is not None:
        banlist = extract_banlist_from_profile(profile_md)
        leak = None
        if banlist and clues:
            for c in clues:
                if not isinstance(c, dict):
                    continue
                d = c.get("difficulty", 0)
                if d not in (1, 2, 3, 4, 5):
                    continue
                text = c.get("text", "")
                for ban in banlist:
                    if not ban or len(ban) < 2:
                        continue
                    if ban in text:
                        leak = (d, ban)
                        break
                if leak:
                    break
        if not leak:
            score += 1
        else:
            warnings.append(f"难度 {leak[0]} 含 profile banlist 词 '{leak[1]}'")

    # 8. 信息密度梯度 (T5): d1-5 每条的具体名词数 ≤ 该难度阈值
    if clues:
        leak = None
        for c in clues:
            if not isinstance(c, dict):
                continue
            d = c.get("difficulty", 0)
            if d not in SPECIFIC_TERM_THRESHOLDS:
                continue
            text = c.get("text", "")
            n = count_specific_terms(text)
            thr = SPECIFIC_TERM_THRESHOLDS[d]
            if n > thr:
                leak = (d, n, thr)
                break
        if not leak:
            score += 1
        else:
            warnings.append(f"难度 {leak[0]} 信息密度过高 (具体名词 {leak[1]} > 阈值 {leak[2]})")

    return score, max_score, warnings


# =====  T6: LLM-as-judge =====

JUDGE_PROMPT_TEMPLATE = """你是中国历史人物线索质量审稿员。给定 aliases + banlist + 7 clues, 为每条 clue 输出 verdict。

verdict 标准 (T14 第二轮灰度后, 进一步放宽 d6/d7 整字 alias):
**违规** (任一触发, 严格 d1-d5):
- d1-d5 clue 含 aliases 整字 (e.g. 完整 "东坡居士" 出现)
- d1-d5 clue 含 aliases **≥ 3 字** 子串 (e.g. "长春居" 3字子串 ⊂ "长春居士" 违规;"高宗"/"弘历" 2字 不算违规)
- d1-d5 clue 含 banlist 中典故/作品名 (d6-d7 求救范围允许 banlist)
- d1 clue 含朝代名 (汉/唐/宋/元/明/清/三国 等)

**可疑** (软违规, 不阻 retry):
- clue 长度 < 20 字 或 > 80 字
- 难度梯度与编号不符 (如 d1 比 d5 还具体)
- d6-d7 含 aliases 整字或 ≥ 3 字子串 (求救范围设计本来允许暴露, 标可疑提醒但不阻塞)

**合规**: 其他

输出严格 JSON (无 markdown 包裹):
{{
  "verdicts": [
    {{"d": 1, "verdict": "<合规|可疑|违规>", "reason": "..."}},
    {{"d": 2, "verdict": "...", "reason": "..."}},
    ...
  ]
}}

aliases: {aliases}

banlist (典故/作品, 仅 d1-5 禁出现):
{banlist}

7 条 clues:
{clues}
"""


def call_judge_llm(model: str, system: str, user: str) -> str:
    """调云雾 LLM (production)。返回 content 字符串。"""
    api_key = os.environ.get("YUNWU_API_KEY")
    base_url = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    if not api_key:
        raise RuntimeError("YUNWU_API_KEY 缺失")
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_judge_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


def judge_clues_llm(figure: dict, profile_md: str | None, model: str, llm_call_fn=None) -> dict:
    """LLM judge 1 figure 的 7 条 clues, 返回 {verdicts: [...]} dict.

    llm_call_fn(model, system, user) -> str. 默认用 call_judge_llm (production);
    单测 mock 时传自定义函数.
    """
    if llm_call_fn is None:
        llm_call_fn = call_judge_llm

    aliases = figure.get("aliases") or []
    clues = figure.get("clues") or []
    banlist = extract_banlist_from_profile(profile_md) if profile_md else []

    aliases_str = ", ".join(aliases) or "(无)"
    banlist_str = "\n".join(f"- {b}" for b in banlist) or "(无)"
    clues_str = "\n".join(
        f"d{c['difficulty']}: {c['text']}"
        for c in clues if isinstance(c, dict)
    )

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        aliases=aliases_str, banlist=banlist_str, clues=clues_str
    )
    content = llm_call_fn(
        model,
        "你是中国历史人物线索质量审稿员, 严格 JSON 输出, 不解释。",
        prompt,
    )
    return parse_judge_json(content)


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
    parser.add_argument("--profiles-dir", default=None,
                        help="profile.md 所在目录 (例: src/lib/data/profiles/). 给定时启用 check #7 (T4)")
    parser.add_argument("--with-judge", action="store_true",
                        help="启用 LLM-as-judge 二次审 (T6, 慢, 烧 LLM 成本)")
    parser.add_argument("--judge-model", default="gemini-3.1-flash-lite",
                        help="judge 用的 LLM model id")
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

    profiles_dir = Path(args.profiles_dir) if args.profiles_dir else None
    if profiles_dir and not profiles_dir.exists():
        print(f"⚠️ --profiles-dir {profiles_dir} 不存在, check #7 跳过")
        profiles_dir = None

    judge_stats = {"合规": 0, "可疑": 0, "违规": 0, "error": 0}

    for i, f in enumerate(figures, 1):
        name = f.get("name", "?")
        profile_md = None
        if profiles_dir:
            fid = f.get("id") or name
            p = profiles_dir / f"{fid}.md"
            if p.exists():
                profile_md = p.read_text(encoding="utf-8")
        score, max_score, warnings = check_figure(f, profile_md)
        status = "✅" if score == max_score else ("⚠️" if score >= max_score - 2 else "❌")
        print(f"{status} [{i:2}] {name:<10}  {score}/{max_score}")

        # T6: judge (informational, not counted in score)
        judge_result = None
        if args.with_judge:
            try:
                judge_result = judge_clues_llm(f, profile_md, args.judge_model)
                for v in judge_result.get("verdicts", []):
                    vd = v.get("verdict", "")
                    if vd in judge_stats:
                        judge_stats[vd] += 1
                if args.verbose:
                    for v in judge_result.get("verdicts", []):
                        icon = {"合规": "✓", "可疑": "?", "违规": "✗"}.get(v.get("verdict"), "?")
                        print(f"      🤖 {icon} d{v.get('d')}: {v.get('verdict')} — {(v.get('reason') or '')[:70]}")
            except Exception as e:
                judge_stats["error"] += 1
                print(f"      🤖 judge 失败: {type(e).__name__}: {str(e)[:80]}")
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
    if args.with_judge:
        total_judged = sum(judge_stats.values())
        print(f"🤖 LLM-as-judge 汇总 ({total_judged} 条 clue 中):")
        for k, v in judge_stats.items():
            if v:
                print(f"   - {k}: {v}")
    print(f"{'=' * 60}")

    if args.strict and issues_count > 0:
        print(f"\n❌ --strict 模式 + {issues_count} 个 figure 有 issue", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
