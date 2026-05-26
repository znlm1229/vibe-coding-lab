#!/usr/bin/env python3
"""
T1: 半自动生成 history_index.json (50 现有 figure 的二十四史本传 mapping).

强 LLM 一次输入 50 figure name → 输出 JSON mapping → verify wikisource page 存在 → 写 history_index.json.

用法:
  python scripts/gen_history_index.py --strong-llm deepseek-v3.2
  python scripts/gen_history_index.py --strong-llm claude-haiku-4-5-20251001 --no-verify

输出: scripts/data/history_index.json
"""

import argparse, json, os, re, sys, time
from pathlib import Path
import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
FIGURES_PATH = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
OUTPUT_PATH = PROJECT_ROOT / "scripts" / "data" / "history_index.json"
LLM_KEY = os.environ.get("YUNWU_API_KEY")
LLM_BASE = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE.endswith("/v1"):
    LLM_BASE += "/v1"
UA = "guess-figure-history-index/0.1 (vibe-coding-lab; T1)"


def load_figure_names() -> list[str]:
    figures = json.loads(FIGURES_PATH.read_text(encoding="utf-8"))
    return [f["name"] for f in figures]


PROMPT_TEMPLATE = """你是中国古籍研究助手。给定一组中国历史人物,输出每个人物在二十四史(含清史稿,共 25 史)中的本传位置。

25 史 (繁体): 史記 / 漢書 / 後漢書 / 三國志 / 晉書 / 宋書 / 南齊書 / 梁書 / 陳書 / 魏書 / 北齊書 / 周書 / 隋書 / 南史 / 北史 / 舊唐書 / 新唐書 / 舊五代史 / 新五代史 / 宋史 / 遼史 / 金史 / 元史 / 明史 / 清史稿

输出严格 JSON (无 markdown 包裹), key 是简体人物名, value 是 dict:
{{
  "人物名": {{
    "wikisource_page": "<繁体页名 或 null>",
    "is_合传": <true 或 false>,
    "biography_name": "<简体传名>"
  }}
}}

要求:
1. **Wikisource 中文版页名一律繁体**(例: 三國志/卷35, 史記/卷六十三, 漢書/卷100上, 新唐書/卷202)。
2. 卷号通常用阿拉伯数字 + 可选中文上中下后缀。
3. 不确定卷号时, 优先 wikisource_page = null 而非乱猜(false positive 比 false negative 危害大)。
4. 鲁迅(1881-1936)等近代人 → wikisource_page = null, biography_name = "(近代人物, 无正史本传)"
5. 孙中山(1866-1925)→ 清史稿可能无本传,如不确定设 null。
6. 合传(如老子与韩非合传)→ is_合传 = true, biography_name = "老子韩非列传"
7. 杨贵妃 → 旧唐书或新唐书后妃传,is_合传 = true。

输入 {n} 个人物:
{names}

直接输出 JSON, 简体人物名作 key, 不要解释。
"""


def call_strong_llm(model, prompt):
    t0 = time.time()
    r = requests.post(f"{LLM_BASE}/chat/completions",
                      headers={"Authorization": f"Bearer {LLM_KEY}",
                               "Content-Type": "application/json"},
                      json={"model": model,
                            "messages": [
                                {"role": "system", "content": "你是中国古籍研究助手, 严格按 JSON 输出, 不解释。"},
                                {"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "max_tokens": 8000},
                      timeout=300)
    latency = round(time.time() - t0, 2)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {}), latency


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            text = m.group(0)
    return json.loads(text)


# 25 史的简体 → 繁体史书名 (LLM 输出不稳定, 简繁都要兼容)
BOOK_S2T = {
    "史记": "史記", "汉书": "漢書", "后汉书": "後漢書", "三国志": "三國志",
    "晋书": "晉書", "宋书": "宋書", "南齐书": "南齊書", "梁书": "梁書",
    "陈书": "陳書", "魏书": "魏書", "北齐书": "北齊書", "周书": "周書",
    "隋书": "隋書", "南史": "南史", "北史": "北史",
    "旧唐书": "舊唐書", "新唐书": "新唐書",
    "旧五代史": "舊五代史", "新五代史": "新五代史",
    "宋史": "宋史", "辽史": "遼史", "金史": "金史",
    "元史": "元史", "明史": "明史", "清史稿": "清史稿",
}
BOOK_T2S = {t: s for s, t in BOOK_S2T.items()}

CN_DIGITS = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}

def _cn_num_to_int(s: str) -> int | None:
    """解析中文数字 (限二十四史卷号常见范围 1-300)。"""
    s = s.strip()
    if not s: return None
    # "一百三十五" / "一百" / "三十" / "三十五" / "十" / "十五" / "五"
    if "百" in s:
        parts = s.split("百")
        h_part = parts[0] or "一"  # "百" 前 empty = 一百
        rest = parts[1] if len(parts) > 1 else ""
        h = CN_DIGITS.get(h_part)
        if h is None: return None
        if not rest: return h * 100
        if "十" in rest:
            t_parts = rest.split("十")
            t = CN_DIGITS.get(t_parts[0]) if t_parts[0] else 1
            o = CN_DIGITS.get(t_parts[1]) if len(t_parts) > 1 and t_parts[1] else 0
            if t is None or o is None: return None
            return h * 100 + t * 10 + o
        o = CN_DIGITS.get(rest)
        return (h * 100 + o) if o is not None else None
    if "十" in s:
        t_parts = s.split("十")
        t = CN_DIGITS.get(t_parts[0]) if t_parts[0] else 1
        o = CN_DIGITS.get(t_parts[1]) if len(t_parts) > 1 and t_parts[1] else 0
        if t is None or o is None: return None
        return t * 10 + o
    return CN_DIGITS.get(s)


def _int_to_cn_num(n: int) -> str:
    """整数 → 中文数字 (1-300 范围)。"""
    if n < 0 or n > 999: return str(n)
    inv = {v: k for k, v in CN_DIGITS.items()}
    if n == 0: return "零"
    if n < 11: return inv[n]
    if n < 20: return "十" + (inv[n - 10] if n > 10 else "")
    if n < 100:
        t, o = divmod(n, 10)
        return inv[t] + "十" + (inv[o] if o else "")
    h, rest = divmod(n, 100)
    out = inv[h] + "百"
    if rest == 0: return out
    if rest < 10: return out + inv[rest]
    if rest < 20: return out + "十" + (inv[rest - 10] if rest > 10 else "")
    t, o = divmod(rest, 10)
    return out + inv[t] + "十" + (inv[o] if o else "")


def _gen_page_candidates(page_name: str) -> list[str]:
    """给定 LLM 输出的 page name, 生成多种命名 variant 试探(简繁书名 × 中阿数字 × 卷上中下后缀)。"""
    candidates = [page_name]
    m = re.match(r"^(.+?)/卷([^/]+?)(上|中|下)?$", page_name)
    if not m:
        return candidates
    book, num_part, suffix = m.group(1), m.group(2), m.group(3) or ""

    # 简繁书名 variant
    book_variants = {book}
    if book in BOOK_S2T:
        book_variants.add(BOOK_S2T[book])
    if book in BOOK_T2S:
        book_variants.add(BOOK_T2S[book])

    # 数字 variant
    arabic_num = None
    cn_num = None
    if num_part.isdigit():
        arabic_num = int(num_part)
        cn_num = _int_to_cn_num(arabic_num)
    else:
        cn_num_val = _cn_num_to_int(num_part)
        if cn_num_val:
            arabic_num = cn_num_val
            cn_num = num_part

    num_variants = []
    if arabic_num is not None:
        num_variants.append(str(arabic_num))
    if cn_num:
        num_variants.append(cn_num)
    if not num_variants:
        num_variants.append(num_part)

    for b in book_variants:
        for n in num_variants:
            for suf in [suffix, "", "上", "下"]:
                cand = f"{b}/卷{n}{suf}"
                if cand and cand not in candidates:
                    candidates.append(cand)
    return candidates


def verify_wikisource_page(page_name: str, timeout: float = 20.0) -> tuple[bool, str | None]:
    """检查 Wikisource 页面是否存在 (用 action=parse, 自动 follow redirect)。

    返回 (exists, resolved_page_name)。失败时 resolved_page_name=None。
    试探多种 page name variant (中文数字 / 阿拉伯 / 卷上下后缀)。
    """
    if not page_name:
        return False, None

    for candidate in _gen_page_candidates(page_name):
        try:
            r = requests.get("https://zh.wikisource.org/w/api.php",
                             params={"action": "parse", "page": candidate, "format": "json",
                                     "prop": "wikitext", "redirects": "true"},
                             headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code != 200:
                continue
            data = r.json()
            if "error" in data:
                continue
            wt = data.get("parse", {}).get("wikitext", {}).get("*", "")
            if len(wt) > 100:  # 非空 + 非 stub
                resolved = data.get("parse", {}).get("title", candidate)
                return True, resolved
        except Exception:
            continue
    return False, None


def main():
    parser = argparse.ArgumentParser(description="T1: 生成 history_index.json")
    parser.add_argument("--strong-llm", default="deepseek-v3.2", help="强 LLM model")
    parser.add_argument("--no-verify", action="store_true", help="跳过 wikisource page 验证")
    args = parser.parse_args()

    if not LLM_KEY:
        raise SystemExit("❌ 缺 YUNWU_API_KEY")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    names = load_figure_names()
    print(f"📥 读 figures.json: {len(names)} 个 figure")

    prompt = PROMPT_TEMPLATE.format(n=len(names),
                                     names="\n".join(f"{i+1}. {n}" for i, n in enumerate(names)))
    print(f"🤖 调强 LLM ({args.strong_llm}) 生成 mapping...")
    content, usage, latency = call_strong_llm(args.strong_llm, prompt)
    print(f"  ✓ {latency}s, usage={usage}")

    try:
        mapping = parse_json(content)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse 失败: {e}")
        print(f"raw 前 500: {content[:500]}")
        raw_path = OUTPUT_PATH.with_suffix(".raw.txt")
        raw_path.write_text(content, encoding="utf-8")
        print(f"raw 保存至 {raw_path}")
        sys.exit(1)

    print(f"\n📊 LLM 输出 {len(mapping)} entry")
    non_null = sum(1 for v in mapping.values() if v and v.get("wikisource_page"))
    print(f"  - 有 wikisource_page: {non_null}/{len(mapping)} ({100*non_null/len(mapping):.0f}%)")

    missing = [n for n in names if n not in mapping]
    if missing:
        print(f"⚠️ LLM 输出漏了 {len(missing)} 个 figure: {missing}")
        for n in missing:
            mapping[n] = None

    extra = [n for n in mapping if n not in names]
    if extra:
        print(f"⚠️ LLM 输出多了 {len(extra)} 个不在 figures.json 的 entry: {extra}")
        for n in extra:
            del mapping[n]

    if not args.no_verify:
        print(f"\n🔍 verify wikisource pages 实际存在 (尝试多种 variant, sleep 1.5s 每个 + 1 次 retry)...")
        verified = 0
        unverified = []
        resolved_changes = []
        for name, info in mapping.items():
            if not info or not info.get("wikisource_page"):
                continue
            original = info["wikisource_page"]
            ok, resolved = verify_wikisource_page(original)
            if not ok:
                time.sleep(2.0)  # cooldown + retry once
                ok, resolved = verify_wikisource_page(original)
            if ok:
                verified += 1
                info["_verified"] = True
                if resolved and resolved != original:
                    resolved_changes.append((name, original, resolved))
                    info["wikisource_page"] = resolved
            else:
                # 策略改: 不删 page, 标 _verified=False, production fetch 容错
                unverified.append((name, original))
                info["_verified"] = False
            time.sleep(1.5)

        print(f"  ✓ verified: {verified}")
        if resolved_changes:
            print(f"  ↻ page name 改写 (LLM 输出 → 实际 Wikisource): {len(resolved_changes)}")
            for name, orig, res in resolved_changes[:10]:
                print(f"    - {name}: {orig} → {res}")
        if unverified:
            print(f"  ? unverified (保留 page name + 标 _verified=false, production fetch 时容错): {len(unverified)}")
            for name, page in unverified[:10]:
                print(f"    - {name}: {page}")

    final_with_page = sum(1 for v in mapping.values() if v and v.get("wikisource_page"))
    final_verified = sum(1 for v in mapping.values() if v and v.get("_verified") is True)
    print(f"\n📊 最终统计:")
    print(f"  - 有 page name (LLM declared): {final_with_page}/{len(names)} ({100*final_with_page/len(names):.0f}%)")
    print(f"  - 已 verify 通过: {final_verified}/{len(names)} ({100*final_verified/len(names):.0f}%)")
    print(f"  - production fetch 时自动容错: _verified=False 的 page 拉不到则走 fallback (仅维基+Wikidata)")

    OUTPUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 保存至 {OUTPUT_PATH}")
    print(f"\n💡 spot check 候选 (随机抽 5 个让用户验证):")
    verified_names = [n for n, v in mapping.items() if v and v.get("wikisource_page")]
    import random
    sample = random.sample(verified_names, min(5, len(verified_names)))
    for n in sample:
        v = mapping[n]
        print(f"  - {n} → https://zh.wikisource.org/wiki/{v['wikisource_page']} ({v.get('biography_name')})")


if __name__ == "__main__":
    main()
