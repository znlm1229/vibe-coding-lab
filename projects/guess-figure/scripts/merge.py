#!/usr/bin/env python3
"""
合并新批次 figures 到主题库 src/lib/data/figures.json（T3 生产版）。

功能：
- 按 id 去重（新批次中跟主库已有的相同 id 跳过）
- 合并后按 id 排序
- schema 校验（aliases 数 / clues 数 / 难度齐 / 必要字段）
- 报告：合并前后人物数 / 新增列表 / 重复跳过列表 / schema 不合规警告
- 支持 --dry-run 仅预览不写

跑法:
  python scripts/merge.py figures-new.json
  python scripts/merge.py figures-batch1.json --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MAIN_DB = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"


def validate_figure(f: dict) -> list[str]:
    """简单 schema 校验，返回 issue list（空 list 表示通过）。"""
    issues = []
    if not f.get("id"):
        issues.append("缺 id")
    if not f.get("name"):
        issues.append("缺 name")
    aliases = f.get("aliases") or []
    if not (3 <= len(aliases) <= 5):
        issues.append(f"aliases 数 {len(aliases)} 不在 3-5")
    clues = f.get("clues") or []
    if len(clues) != 7:
        issues.append(f"clues 数 {len(clues)} ≠ 7")
    diffs = sorted([c.get("difficulty") for c in clues if isinstance(c, dict)])
    if diffs != [1, 2, 3, 4, 5, 6, 7]:
        issues.append(f"难度分布 {diffs} ≠ [1-7]")
    if not f.get("wikidata_id"):
        issues.append("缺 wikidata_id")
    if not f.get("wiki_url"):
        issues.append("缺 wiki_url")
    return issues


def main():
    parser = argparse.ArgumentParser(description="合并新批次 figures 到主题库")
    parser.add_argument("new_file", help="新 figures JSON 文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入")
    args = parser.parse_args()

    new_path = Path(args.new_file)
    if not new_path.exists():
        raise SystemExit(f"❌ 新 figures 文件不存在: {new_path}")

    try:
        new_figures = json.loads(new_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"❌ 新文件 JSON 解析失败: {e}")

    if not isinstance(new_figures, list):
        raise SystemExit("❌ 新 figures 必须是 JSON 数组")

    print(f"📥 读取新批次: {len(new_figures)} 个 figures（{new_path}）")

    # 校验新批次 schema
    invalid = []
    for i, f in enumerate(new_figures):
        issues = validate_figure(f)
        if issues:
            invalid.append((i, f.get("name", "?"), issues))
    if invalid:
        print(f"\n⚠️ 新批次有 {len(invalid)} 个 figure schema 不合规:")
        for idx, name, issues in invalid:
            print(f"  [{idx}] {name}: {', '.join(issues)}")
        if not args.dry_run:
            ans = input("\n继续合并这些不合规的 figure？(y/N): ").strip().lower()
            if ans != "y":
                raise SystemExit("取消合并")

    # 读主库
    if MAIN_DB.exists():
        try:
            main_figures = json.loads(MAIN_DB.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"❌ 主库 {MAIN_DB} JSON 解析失败: {e}")
        if not isinstance(main_figures, list):
            raise SystemExit(f"❌ 主库 {MAIN_DB} 不是 JSON 数组")
    else:
        print(f"📂 主库 {MAIN_DB} 不存在，将首次创建")
        main_figures = []
        MAIN_DB.parent.mkdir(parents=True, exist_ok=True)

    existing_ids = {f.get("id") for f in main_figures if f.get("id")}

    new_added = []
    dups_skipped = []
    for f in new_figures:
        fid = f.get("id")
        if not fid:
            print(f"  ⚠️ skip：缺 id 的 figure: {f.get('name', '?')}")
            continue
        if fid in existing_ids:
            dups_skipped.append(f)
        else:
            new_added.append(f)
            existing_ids.add(fid)

    merged = sorted(main_figures + new_added, key=lambda x: x.get("id", ""))

    print(f"\n📊 合并结果:")
    print(f"  主库原有: {len(main_figures)}")
    print(f"  新增: {len(new_added)}")
    if new_added:
        print(f"    {[f['name'] for f in new_added]}")
    print(f"  重复跳过: {len(dups_skipped)}")
    if dups_skipped:
        print(f"    {[f.get('name') for f in dups_skipped]}")
    print(f"  合并后总计: {len(merged)}")

    if args.dry_run:
        print("\n🔬 --dry-run 模式，未写入主库")
        return

    if not new_added:
        print("\n⏭️ 没有新增 figure，跳过写入")
        return

    MAIN_DB.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ 已写入: {MAIN_DB}")
    print(f"💡 检查 git diff 看变更；commit 用 `task-T5.N: 题库 +{len(new_added)} 人物` 前缀")


if __name__ == "__main__":
    main()
