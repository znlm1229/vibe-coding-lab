#!/usr/bin/env python3
"""
T19: regen_diff 自动对比 v1 vs v2.

读 v1 figures.json + v2 candidates + 50 profile.md,跑 quality_check 双方,
产 scripts/data/regen_diff.md 含逐 figure 决策。

跑法:
  python scripts/regen_diff.py

输出: scripts/data/regen_diff.md
"""

import json
import sys
from pathlib import Path

# 强制 stdout UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from quality_check import check_figure  # noqa: E402

V1_FIGURES = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
V2_CANDIDATES = PROJECT_ROOT / "scripts" / "data" / "figures.v2-candidates.json"
PROFILES_DIR = PROJECT_ROOT / "src" / "lib" / "data" / "profiles"
FAILED_FIGURES = PROJECT_ROOT / "scripts" / "data" / "failed_figures.json"
OUTPUT = PROJECT_ROOT / "scripts" / "data" / "regen_diff.md"


def load_profile_md(figure_name: str) -> str | None:
    p = PROFILES_DIR / f"{figure_name}.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def main():
    v1_data = json.loads(V1_FIGURES.read_text(encoding="utf-8"))
    v1_by_name = {f["name"]: f for f in v1_data}

    v2_data = json.loads(V2_CANDIDATES.read_text(encoding="utf-8"))
    v2_by_name = {f["name"]: f for f in v2_data}

    failed_list = []
    if FAILED_FIGURES.exists():
        failed_list = json.loads(FAILED_FIGURES.read_text(encoding="utf-8"))
    failed_names = {f["name"] for f in failed_list}

    rows = []
    采用_count = 拒绝_count = failed_count = 0

    for v1_figure in v1_data:
        name = v1_figure["name"]
        # v1 跑 quality_check (无 profile, max=7)
        v1_score, v1_max, v1_warns = check_figure(v1_figure, profile_md=None)

        if name in v2_by_name:
            v2_figure = v2_by_name[name]
            profile_md = load_profile_md(name)
            v2_score, v2_max, v2_warns = check_figure(v2_figure, profile_md=profile_md)

            # 决策: v2 比例 ≥ v1 比例 且 v2 violations ≤ v1 → 采用 v2
            v1_ratio = v1_score / v1_max if v1_max else 0
            v2_ratio = v2_score / v2_max if v2_max else 0
            if v2_ratio >= v1_ratio and len(v2_warns) <= len(v1_warns):
                decision = "✅ 候选采用 v2"
                采用_count += 1
            else:
                decision = "🔄 候选拒绝 (保留 v1)"
                拒绝_count += 1
        else:
            v2_score, v2_max = None, None
            v2_warns = []
            decision = "❌ v2 failed (保留 v1)"
            failed_count += 1

        rows.append({
            "name": name,
            "v1_score": v1_score, "v1_max": v1_max, "v1_warns": v1_warns,
            "v2_score": v2_score, "v2_max": v2_max, "v2_warns": v2_warns,
            "decision": decision,
        })

    md = []
    md.append("# regen_diff: v1 vs v2 对比 (50 旧 figure)\n")
    md.append("- **v1** = `src/lib/data/figures.json` (现版本, 旧)")
    md.append("- **v2** = `scripts/data/figures.v2-candidates.json` (T18 跑出, 36 通过 + 14 failed)")
    md.append("- **score 算法**: 升级版 quality_check (v1 无 profile max=7; v2 有 profile max=8)")
    md.append("- **自动决策**: v2 score 比例 ≥ v1 比例 且 v2 violations ≤ v1 → 采用 v2, 否则保留 v1\n")

    md.append("## 自动决策汇总\n")
    md.append(f"- ✅ 候选采用 v2: **{采用_count}** / 50")
    md.append(f"- 🔄 候选拒绝 (v2 不如 v1, 保留 v1): **{拒绝_count}** / 50")
    md.append(f"- ❌ v2 failed (保留 v1): **{failed_count}** / 50")
    md.append(f"- 合计: {采用_count + 拒绝_count + failed_count} = 50 ✓\n")

    md.append("## 逐 figure 详情\n")
    md.append("| # | name | v1 score | v1 violations | v2 score | v2 violations | 决策 |")
    md.append("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        v1_s = f"{r['v1_score']}/{r['v1_max']}"
        v2_s = f"{r['v2_score']}/{r['v2_max']}" if r["v2_score"] is not None else "(v2 failed)"
        v1_w = "; ".join(r["v1_warns"])[:80] or "(无)"
        v2_w = "; ".join(r["v2_warns"])[:80] or "(无)"
        md.append(f"| {i} | {r['name']} | {v1_s} | {v1_w} | {v2_s} | {v2_w} | {r['decision']} |")
    md.append("")

    md.append("## 用户 review 流程\n")
    md.append("**T20 ★ 关卡** — 请你 review 上表后给指令(3 种回应):\n")
    md.append("1. **\"全部按自动决策\"** → AI 直接 produce final figures.json (采用 v2 的换 v2 entry, 其余保留 v1)")
    md.append("2. **\"采用所有 v2 candidates\"** → 36 个 v2 全采用, 14 failed 保留 v1")
    md.append("3. **\"采用 v2 除了 X / Y / Z\"** → 自定义 reject 列表\n")
    md.append("拍板后 AI 进 T21 (figures.v1.json 备份) + 写 final figures.json。\n")

    OUTPUT.write_text("\n".join(md), encoding="utf-8")
    print(f"✅ 写入 {OUTPUT}")
    print(f"📊 决策: 采用 v2 {采用_count} / 拒绝 {拒绝_count} / failed {failed_count} = 50")


if __name__ == "__main__":
    main()
