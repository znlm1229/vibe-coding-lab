#!/usr/bin/env python3
"""
T3+ quality_check.py 升级项单测 (stdlib unittest, 无新 deps)。

跑法:
  python scripts/tests/test_quality_check.py
  python -m unittest scripts.tests.test_quality_check -v
"""

import json
import sys
import unittest
from pathlib import Path

# allow `from quality_check import ...` when running standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quality_check import (
    check_figure,
    _alias_substrings,
    extract_banlist_from_profile,
    count_specific_terms,
    judge_clues_llm,
    parse_judge_json,
)


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
        score, _, warnings = check_figure(f)
        leak_warn = [w for w in warnings if "子串" in w and "云长" in w]
        self.assertTrue(leak_warn, f"应报 d7 alias 子串穿底,实际 warnings={warnings}")

    def test_d6_substring_穿底_alias完整出现(self):
        """d6 含 alias 完整字符 → 应判违规"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={6: "三国时蜀汉丞相,卧龙先生,后封武乡侯。"},
        )
        score, _, warnings = check_figure(f)
        leak_warn = [w for w in warnings if "子串" in w and "卧龙" in w]
        self.assertTrue(leak_warn, f"应报 d6 alias 完整出现,实际 warnings={warnings}")

    def test_d6_d7_clean_no_warning(self):
        """d6/d7 无 alias 子串 → check #6 通过"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={6: "他是蜀汉政权的核心支柱,后人尊为某代名相。",
                             7: "他是三国时期蜀汉丞相,献上三分天下之策。"},
        )
        score, _, warnings = check_figure(f)
        # 注意:d6/d7 都不含子串。但其他 check 可能触发(d1-5 可能不含 aliases 整字,看具体 placeholder)
        check6_warns = [w for w in warnings if "子串" in w]
        self.assertFalse(check6_warns, f"不该报子串穿底,实际 warnings={warnings}")

    def test_single_char_alias_not_flagged(self):
        """单字 alias 在 d6/d7 出现不算违规 (避免 '关' / '关于' false positive)"""
        f = _make_figure(
            aliases=["关羽伯爵", "关"],  # "关" 是单字 alias
            clues_text_by_d={6: "关于他的故事,在民间流传很广,被尊为某神明。"},
        )
        score, _, warnings = check_figure(f)
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
        score, _, warnings = check_figure(f)
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
        score, _, warnings = check_figure(f)
        皇帝_warns = [w for w in warnings if "'皇帝'" in w]
        self.assertFalse(皇帝_warns, "'皇帝' 子串属 stopword 不该被 flag")

    def test_丞相_stopword_not_flagged(self):
        """'丞相' 是职官通用词 → 不应 flag"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛丞相"],  # 假设含 "诸葛丞相" alias
            clues_text_by_d={6: "这位丞相在五丈原对峙司马懿。"},
        )
        score, _, warnings = check_figure(f)
        丞相_warns = [w for w in warnings if "'丞相'" in w]
        self.assertFalse(丞相_warns, "'丞相' 子串属 stopword 不该被 flag")

    def test_specific_alias_still_flagged(self):
        """虽然加 stopword,但'云长'/'卧龙' 等专指 alias 仍要 flag"""
        f = _make_figure(
            aliases=["关云长", "皇帝"],  # 同时含 alias "关云长" 和 stopword 词
            clues_text_by_d={7: "他字云长,是蜀汉皇帝麾下的大将。"},
        )
        score, _, warnings = check_figure(f)
        # '云长' 不在 stopword → 应 flag;'皇帝' 在 stopword → 不 flag
        云长_warns = [w for w in warnings if "'云长'" in w]
        皇帝_warns = [w for w in warnings if "'皇帝'" in w]
        self.assertTrue(云长_warns, "'云长' 是专指 alias 子串,应 flag")
        self.assertFalse(皇帝_warns, "'皇帝' 是 stopword,不 flag")


SAMPLE_PROFILE = """# 诸葛亮

## 基本信息
- 字 / 号: 字孔明, 号卧龙

## 主要事迹
- 207 年隆中对

## 典故 / 标志事件
- 三顾茅庐:刘备三次拜访诸葛亮于隆中草庐
- 隆中对(草庐对):提出三分天下战略
- 鞠躬尽瘁,死而后已:出师表名句
- 五丈原:北伐病逝

## 关键作品
- 《出师表》:北伐前上奏后主
- 木牛流马:山地运输工具
- 八阵图:阵法

## 反差 / 鲜为人知点
- 娶丑女为妻
"""


class TestExtractBanlistFromProfile(unittest.TestCase):
    """T4 — helper: 从 profile.md 抽 banlist 词"""

    def test_extracts_典故_section(self):
        bans = extract_banlist_from_profile(SAMPLE_PROFILE)
        self.assertIn("三顾茅庐", bans)
        self.assertIn("五丈原", bans)

    def test_extracts_关键作品_section(self):
        bans = extract_banlist_from_profile(SAMPLE_PROFILE)
        self.assertIn("《出师表》", bans)
        self.assertIn("木牛流马", bans)
        self.assertIn("八阵图", bans)

    def test_strips_parentheses(self):
        """'草庐对(隆中对)' → 'XXX' 不该带括号"""
        bans = extract_banlist_from_profile(SAMPLE_PROFILE)
        # 隆中对 是括号内, 实际 extract 出的是 "隆中对" 还是 "草庐对"?
        # 我的实现: 去括号后取冒号前. 原文 "隆中对(草庐对):提出三分天下战略" → "隆中对" + 空 → "隆中对"
        # 等等, 注意 # SAMPLE 写的是 "隆中对(草庐对):..." 实际我写的是 "隆中对(草庐对):提出..."
        # 不,等等: SAMPLE_PROFILE 写的 "- 隆中对(草庐对):提出三分天下战略" → 去括号 "隆中对:提出..." → 取 ":" 前 "隆中对"
        self.assertIn("隆中对", bans)
        # 不该有带括号的项
        for b in bans:
            self.assertNotIn("(", b)
            self.assertNotIn("（", b)

    def test_handles_comma_separator(self):
        """'鞠躬尽瘁,死而后已' → '鞠躬尽瘁'"""
        bans = extract_banlist_from_profile(SAMPLE_PROFILE)
        self.assertIn("鞠躬尽瘁", bans)

    def test_empty_profile(self):
        self.assertEqual(extract_banlist_from_profile(""), [])
        self.assertEqual(extract_banlist_from_profile(None or ""), [])


class TestCheck7_D15ProfileBanlist(unittest.TestCase):
    """T4 — check #7: d1-5 不含 profile typology / 作品 banlist"""

    def test_d3_含三顾茅庐_应判违规(self):
        f = _make_figure(
            aliases=["孔明", "卧龙"],
            clues_text_by_d={3: "他在刘备三顾茅庐后才出山辅佐"},
        )
        score, max_score, warnings = check_figure(f, profile_md=SAMPLE_PROFILE)
        self.assertEqual(max_score, 8, "有 profile_md 时 max_score 应为 8 (T5 后)")
        banlist_warns = [w for w in warnings if "profile banlist" in w]
        self.assertTrue(banlist_warns, f"d3 含'三顾茅庐'应被 flag, 实际 warnings={warnings}")

    def test_d2_含木牛流马_应判违规(self):
        f = _make_figure(
            aliases=["孔明", "卧龙"],
            clues_text_by_d={2: "他设计了木牛流马运输工具"},
        )
        score, max_score, warnings = check_figure(f, profile_md=SAMPLE_PROFILE)
        banlist_warns = [w for w in warnings if "'木牛流马'" in w]
        self.assertTrue(banlist_warns, "d2 含'木牛流马'应被 flag")

    def test_d6_含三顾茅庐_不触发check7(self):
        """d6/d7 求救范围允许 banlist (Q4 决议), check #7 只查 d1-5"""
        f = _make_figure(
            aliases=["孔明", "卧龙"],
            clues_text_by_d={6: "他在刘备三顾茅庐后才出山辅佐"},
        )
        score, max_score, warnings = check_figure(f, profile_md=SAMPLE_PROFILE)
        # check #7 不查 d6
        check7_warns = [w for w in warnings if "profile banlist" in w]
        self.assertFalse(check7_warns, "d6 含 banlist 不该触发 check #7")

    def test_no_profile_skip_check7(self):
        """无 profile_md → max_score=7 (T5 后, 跳过 check #7 但 check #8 在)"""
        f = _make_figure(aliases=["孔明", "卧龙"], clues_text_by_d={})
        score, max_score, _ = check_figure(f, profile_md=None)
        self.assertEqual(max_score, 7, "无 profile_md 时 max_score=7 (1-6 + 8)")


class TestCheck8_InfoDensity(unittest.TestCase):
    """T5 — check #8: 信息密度启发式 (具体名词数 vs 难度阈值)"""

    def test_count_specific_terms_book_title(self):
        # 书名号《》计数
        self.assertEqual(count_specific_terms("他写了《出师表》和《诫子书》"), 2)

    def test_count_specific_terms_dynasty(self):
        # 朝代名计数
        self.assertEqual(count_specific_terms("他在三国时期辅佐蜀汉"), 2)

    def test_count_specific_terms_event(self):
        # 历史事件 (XX 之战 / 之乱)
        self.assertEqual(count_specific_terms("赤壁之战与街亭之役都很关键"), 2)

    def test_count_specific_terms_year(self):
        self.assertEqual(count_specific_terms("234年病逝五丈原"), 1)

    def test_d1_too_dense_flagged(self):
        """d1 信息密度过高 → flag"""
        # 阈值 d1=2,放 3 个具体名词
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={1: "他在三国时期参与赤壁之战与街亭之役,留下《出师表》"},
        )
        score, max_score, warnings = check_figure(f)
        density_warns = [w for w in warnings if "信息密度过高" in w and "难度 1" in w]
        self.assertTrue(density_warns, f"d1 含 4 个具体名词(三国/赤壁之战/街亭之役/《出师表》),应 flag,实际 warnings={warnings}")

    def test_d5_within_threshold_ok(self):
        """d5 阈值 6, 含 3 个具体名词 ok"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={5: "他活跃于三国时期辅佐蜀汉君主"},  # 2 朝代名
        )
        score, max_score, warnings = check_figure(f)
        density_warns = [w for w in warnings if "信息密度过高" in w and "难度 5" in w]
        self.assertFalse(density_warns, "d5 含 2 个 specific 不该 flag")

    def test_d6_d7_not_checked(self):
        """d6/d7 求救范围,信息密度不查"""
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={6: "他在三国时期参与赤壁之战、街亭之役、五丈原之役留下《出师表》《诫子书》",
                             7: "他是三国蜀汉丞相"},
        )
        score, max_score, warnings = check_figure(f)
        density_d67_warns = [w for w in warnings if "信息密度过高" in w and ("难度 6" in w or "难度 7" in w)]
        self.assertFalse(density_d67_warns, "d6/d7 不该被 check #8 检查")


class TestMaxScore(unittest.TestCase):
    """T5 — max_score 现 7/8"""

    def test_max_score_7_without_profile(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        _, max_score, _ = check_figure(f, profile_md=None)
        self.assertEqual(max_score, 7, "无 profile_md 时 max_score=7 (1-6 + 8)")

    def test_max_score_8_with_profile(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        _, max_score, _ = check_figure(f, profile_md=SAMPLE_PROFILE)
        self.assertEqual(max_score, 8, "profile_md 给定时 max_score=8")


class TestJudge_T6(unittest.TestCase):
    """T6 — LLM-as-judge 集成 (mock LLM call)"""

    def test_judge_parses_合规_response(self):
        """LLM 返回 7 条 verdict 全合规 → 解析 OK"""
        f = _make_figure(aliases=["孔明", "卧龙"], clues_text_by_d={})
        mock_response = json.dumps({
            "verdicts": [
                {"d": d, "verdict": "合规", "reason": f"d{d} OK"} for d in range(1, 8)
            ]
        })

        def mock_llm(model, system, user):
            # 验证 prompt 中含关键内容
            self.assertIn("aliases:", user)
            self.assertIn("孔明", user)
            self.assertIn("verdict", user)
            return mock_response

        result = judge_clues_llm(f, None, "fake-model", llm_call_fn=mock_llm)
        self.assertEqual(len(result["verdicts"]), 7)
        for v in result["verdicts"]:
            self.assertEqual(v["verdict"], "合规")

    def test_judge_parses_违规_response(self):
        """LLM 返回 d1 违规 → 解析 OK"""
        f = _make_figure(aliases=["孔明"], clues_text_by_d={})
        mock_response = json.dumps({
            "verdicts": [
                {"d": 1, "verdict": "违规", "reason": "d1 含 alias '孔明'"},
                {"d": 2, "verdict": "合规", "reason": "OK"},
                {"d": 3, "verdict": "合规", "reason": "OK"},
                {"d": 4, "verdict": "合规", "reason": "OK"},
                {"d": 5, "verdict": "合规", "reason": "OK"},
                {"d": 6, "verdict": "合规", "reason": "OK"},
                {"d": 7, "verdict": "合规", "reason": "OK"},
            ]
        })

        def mock_llm(model, system, user):
            return mock_response

        result = judge_clues_llm(f, None, "fake-model", llm_call_fn=mock_llm)
        self.assertEqual(result["verdicts"][0]["verdict"], "违规")
        self.assertIn("孔明", result["verdicts"][0]["reason"])

    def test_judge_handles_markdown_wrapped_json(self):
        """LLM 输出 ```json ... ``` 包裹时也能解析"""
        f = _make_figure(aliases=["a"], clues_text_by_d={})
        wrapped = "```json\n" + json.dumps({"verdicts": [{"d": 1, "verdict": "合规", "reason": "OK"}]}) + "\n```"

        def mock_llm(model, system, user):
            return wrapped

        result = judge_clues_llm(f, None, "fake-model", llm_call_fn=mock_llm)
        self.assertEqual(len(result["verdicts"]), 1)

    def test_judge_includes_banlist_in_prompt(self):
        """profile_md 给定时, banlist 应注入 judge prompt"""
        f = _make_figure(aliases=["孔明"], clues_text_by_d={})
        captured_prompt = []

        def mock_llm(model, system, user):
            captured_prompt.append(user)
            return json.dumps({"verdicts": [
                {"d": d, "verdict": "合规", "reason": "OK"} for d in range(1, 8)
            ]})

        judge_clues_llm(f, profile_md=SAMPLE_PROFILE, model="fake-model", llm_call_fn=mock_llm)
        prompt = captured_prompt[0]
        # banlist 应包含 typology section 中的关键词
        self.assertIn("三顾茅庐", prompt, "banlist 应注入 prompt")
        self.assertIn("木牛流马", prompt, "关键作品也应注入")

    def test_judge_prompt_区分_d15_d67(self):
        """JUDGE_PROMPT_TEMPLATE 必须显式区分 d1-5 vs d6-7 规则 (OQ14)"""
        from quality_check import JUDGE_PROMPT_TEMPLATE
        # prompt 应包含两类规则的区分说明
        self.assertIn("d6-d7 求救范围允许 banlist", JUDGE_PROMPT_TEMPLATE)
        self.assertIn("d6-d7 求救范围允许 aliases 子串", JUDGE_PROMPT_TEMPLATE)


class TestExistingChecks(unittest.TestCase):
    """旧 5 项 check 兼容性回归 (确保 T3 加 #6 没破坏旧检测)"""

    def test_aliases_count_3_to_5_ok(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        score, _, _ = check_figure(f)
        # 3 aliases OK,但 clues 是 placeholder,其他可能未必满分
        # 仅看 alias count 不报 warning
        # 因为 placeholder "占位文本不含敏感词" 不会触发 check #4 (没 alias 字符)
        # check #1 应该 +1
        self.assertGreaterEqual(score, 1)

    def test_aliases_count_too_few_warning(self):
        f = _make_figure(aliases=["a"], clues_text_by_d={})
        score, _, warnings = check_figure(f)
        self.assertTrue(any("aliases 数" in w for w in warnings))

    def test_clues_count_7_ok(self):
        f = _make_figure(aliases=["a", "b", "c"], clues_text_by_d={})
        # 7 clues
        score, _, warnings = check_figure(f)
        self.assertFalse(any("clues 数" in w for w in warnings))

    def test_d1_dynasty_warning(self):
        f = _make_figure(
            aliases=["孔明", "卧龙", "诸葛武侯"],
            clues_text_by_d={1: "他生活在三国时期的蜀汉政权,是著名谋士"},
        )
        score, _, warnings = check_figure(f)
        # d1 含"三国"和"蜀汉"朝代关键词
        self.assertTrue(any("朝代名" in w for w in warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
