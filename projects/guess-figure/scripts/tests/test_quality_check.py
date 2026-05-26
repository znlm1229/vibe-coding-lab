#!/usr/bin/env python3
"""
T3+ quality_check.py 升级项单测 (stdlib unittest, 无新 deps)。

跑法:
  python scripts/tests/test_quality_check.py
  python -m unittest scripts.tests.test_quality_check -v
"""

import sys
import unittest
from pathlib import Path

# allow `from quality_check import ...` when running standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quality_check import check_figure, _alias_substrings


def _make_figure(aliases, clues_text_by_d):
    """Helper: 构造 figure dict, clues_text_by_d 是 {难度: 文本} dict"""
    clues = [{"text": clues_text_by_d.get(d, "占位文本不含敏感词"), "difficulty": d}
             for d in range(1, 8)]
    return {"name": "测试人物", "aliases": aliases, "clues": clues}


class TestAliasSubstringsHelper(unittest.TestCase):
    def test_2char_alias(self):
        # "卧龙" 2 字, min_len=2 → ["卧龙"] (整字算子串)
        self.assertEqual(_alias_substrings("卧龙", 2), ["卧龙"])

    def test_3char_alias(self):
        # "关云长" 3 字, min_len=2 → ["关云", "云长", "关云长"]
        subs = _alias_substrings("关云长", 2)
        self.assertIn("关云", subs)
        self.assertIn("云长", subs)
        self.assertIn("关云长", subs)
        # 单字 "关" / "云" / "长" 不应在内 (min_len=2)
        self.assertNotIn("关", subs)
        self.assertNotIn("云", subs)

    def test_1char_alias(self):
        # 单字 alias, min_len=2 → 空
        self.assertEqual(_alias_substrings("关", 2), [])


class TestCheck6_D67AliasSubstring(unittest.TestCase):
    """T3 — check #6: d6/7 不含 aliases 子串 (≥ 2 字)"""

    def test_d7_substring_穿底_关云长(self):
        """关羽 d7 含 alias '关云长' 的子串 '云长' → 应判违规"""
        f = _make_figure(
            aliases=["关云长", "关公", "关二爷", "关帝"],
            clues_text_by_d={7: "他是蜀汉五虎上将之首,字云长,河东解人。"},
        )
        score, warnings = check_figure(f)
        leak_warn = [w for w in warnings if "子串" in w and "云长" in w]
        self.assertTrue(leak_warn, f"应报 d7 alias 子串穿底,实际 warnings={warnings}")

    def test_d6_substring_穿底_alias完整出现(self):
        """d6 含 alias 完整字符 → 应判违规"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={6: "三国时蜀汉丞相,卧龙先生,后封武乡侯。"},
        )
        score, warnings = check_figure(f)
        leak_warn = [w for w in warnings if "子串" in w and "卧龙" in w]
        self.assertTrue(leak_warn, f"应报 d6 alias 完整出现,实际 warnings={warnings}")

    def test_d6_d7_clean_no_warning(self):
        """d6/d7 无 alias 子串 → check #6 通过"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={6: "他是蜀汉政权的核心支柱,后人尊为某代名相。",
                             7: "他是三国时期蜀汉丞相,献上三分天下之策。"},
        )
        score, warnings = check_figure(f)
        # 注意:d6/d7 都不含子串。但其他 check 可能触发(d1-5 可能不含 aliases 整字,看具体 placeholder)
        check6_warns = [w for w in warnings if "子串" in w]
        self.assertFalse(check6_warns, f"不该报子串穿底,实际 warnings={warnings}")

    def test_single_char_alias_not_flagged(self):
        """单字 alias 在 d6/d7 出现不算违规 (避免 '关' / '关于' false positive)"""
        f = _make_figure(
            aliases=["关羽伯爵", "关"],  # "关" 是单字 alias
            clues_text_by_d={6: "关于他的故事,在民间流传很广,被尊为某神明。"},
        )
        score, warnings = check_figure(f)
        # 单字 alias "关" 不该触发子串 check (min_len=2)
        # 注意 "关羽伯爵" 4 字,如果"关羽"出现也会触发 — 但 placeholder 不含
        single_char_warns = [w for w in warnings if "子串 '关'" in w]
        self.assertFalse(single_char_warns, "单字 alias 不该被子串 check 命中")

    def test_d15_substring_should_NOT_trigger_check6(self):
        """d1-5 含 alias 子串 → check #6 不报 (但 check #4 整字会管 d1-5)"""
        f = _make_figure(
            aliases=["关云长", "关公"],
            clues_text_by_d={3: "他曾在战场上斩杀云长之敌"},  # d3 含 "云长" 子串
        )
        score, warnings = check_figure(f)
        # check #6 只查 d6/7, d3 不该触发 check #6
        check6_warns = [w for w in warnings if "子串" in w]
        self.assertFalse(check6_warns, "d3 含子串不该触发 check #6 (它只管 d6/7)")


class TestCheck6_StopwordFalsePositives(unittest.TestCase):
    """T3 — check #6 stopword: 通用职衔不该触发 (避免 '皇帝' 类 false positive)"""

    def test_皇帝_stopword_not_flagged(self):
        """'皇帝' 子串 ⊂ '昭烈皇帝' (alias) → 不应 flag (通用类目词)"""
        f = _make_figure(
            aliases=["刘玄德", "汉昭烈帝", "昭烈皇帝", "汉先主", "烈祖"],
            clues_text_by_d={6: "这位皇帝在白帝城托孤,其子继位。"},
        )
        score, warnings = check_figure(f)
        皇帝_warns = [w for w in warnings if "'皇帝'" in w]
        self.assertFalse(皇帝_warns, "'皇帝' 子串属 stopword 不该被 flag")

    def test_丞相_stopword_not_flagged(self):
        """'丞相' 是职官通用词 → 不应 flag"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛丞相"],  # 假设含 "诸葛丞相" alias
            clues_text_by_d={6: "这位丞相在五丈原对峙司马懿。"},
        )
        score, warnings = check_figure(f)
        丞相_warns = [w for w in warnings if "'丞相'" in w]
        self.assertFalse(丞相_warns, "'丞相' 子串属 stopword 不该被 flag")

    def test_specific_alias_still_flagged(self):
        """虽然加 stopword,但'云长'/'卧龙' 等专指 alias 仍要 flag"""
        f = _make_figure(
            aliases=["关云长", "皇帝"],  # 同时含 alias "关云长" 和 stopword 词
            clues_text_by_d={7: "他字云长,是蜀汉皇帝麾下的大将。"},
        )
        score, warnings = check_figure(f)
        # '云长' 不在 stopword → 应 flag;'皇帝' 在 stopword → 不 flag
        云长_warns = [w for w in warnings if "'云长'" in w]
        皇帝_warns = [w for w in warnings if "'皇帝'" in w]
        self.assertTrue(云长_warns, "'云长' 是专指 alias 子串,应 flag")
        self.assertFalse(皇帝_warns, "'皇帝' 是 stopword,不 flag")


class TestExistingChecks(unittest.TestCase):
    """旧 5 项 check 兼容性回归 (确保 T3 加 #6 没破坏旧检测)"""

    def test_aliases_count_3_to_5_ok(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        score, _ = check_figure(f)
        # 3 aliases OK,但 clues 是 placeholder,其他可能未必满分
        # 仅看 alias count 不报 warning
        # 因为 placeholder "占位文本不含敏感词" 不会触发 check #4 (没 alias 字符)
        # check #1 应该 +1
        self.assertGreaterEqual(score, 1)

    def test_aliases_count_too_few_warning(self):
        f = _make_figure(aliases=["a"], clues_text_by_d={})
        score, warnings = check_figure(f)
        self.assertTrue(any("aliases 数" in w for w in warnings))

    def test_clues_count_7_ok(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        # 7 clues
        score, warnings = check_figure(f)
        self.assertFalse(any("clues 数" in w for w in warnings))

    def test_d1_dynasty_warning(self):
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={1: "他生活在三国时期的蜀汉政权,是著名谋士"},
        )
        score, warnings = check_figure(f)
        # d1 含"三国"和"蜀汉"朝代关键词
        self.assertTrue(any("朝代名" in w for w in warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
