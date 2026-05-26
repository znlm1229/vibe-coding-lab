#!/usr/bin/env python3
"""
T7-T13 generate_figures.py v2 单测 (stdlib unittest + unittest.mock)。

跑法:
  python scripts/tests/test_generate_figures.py
"""

import json
import logging
import sys
import unittest
from pathlib import Path
from unittest import mock

# allow `from generate_figures import ...` when running standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 必须在 import generate_figures 前 mock 模块级 LLM_API_KEY check
import os
os.environ.setdefault("YUNWU_API_KEY", "fake-test-key")

from generate_figures import (
    call_llm,
    validate_profile_sections,
    material_to_text,
    parse_json_safe,
    estimate_cost_cny,
    clues_from_profile,
    judge_and_retry_loop,
    PROFILE_SECTIONS_REQUIRED,
)


SAMPLE_PROFILE_COMPLETE = """# 测试人物

## 基本信息
- 字: 测

## 主要事迹
- 事 1 [重要]

## 性格 / 风格特征
- 性格 1

## 典故 / 标志事件
- 典故 A:描述 A
- 典故 B

## 关键作品
- 《作品 A》

## 关系网
- 老师: 师 1

## 历史评价
- 正面: 评价

## 反差 / 鲜为人知点
- 反差 1
"""


class TestCallLLM_ThinkingModelDefense(unittest.TestCase):
    """AC17 — call_llm 必须 detect thinking model (reasoning_tokens>0 + content 空 → raise)"""

    def test_thinking_model_raises(self):
        """模拟 gemini-2.5-pro 类 thinking model: reasoning_tokens > 0, content = ''"""
        fake_response = {
            "choices": [{
                "message": {"content": ""},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 3000,
                "completion_tokens_details": {"reasoning_tokens": 3000},
            },
        }
        with mock.patch("generate_figures.requests.post") as mock_post:
            mock_post.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: fake_response,
                raise_for_status=lambda: None,
            )
            with self.assertRaises(RuntimeError) as ctx:
                call_llm("gemini-2.5-pro", "sys", "user", log=logging.getLogger())
            self.assertIn("thinking model", str(ctx.exception))

    def test_normal_model_ok(self):
        """正常 model: content 非空, reasoning_tokens = 0 → 返回 content"""
        fake_response = {
            "choices": [{
                "message": {"content": "正常输出"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        with mock.patch("generate_figures.requests.post") as mock_post:
            mock_post.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: fake_response,
                raise_for_status=lambda: None,
            )
            res = call_llm("deepseek-v3.2", "sys", "user", log=logging.getLogger())
            self.assertEqual(res["content"], "正常输出")

    def test_thinking_model_with_content_does_not_raise(self):
        """reasoning_tokens > 0 但 content 非空 → 不 raise (合法情况)"""
        fake_response = {
            "choices": [{
                "message": {"content": "thinking 后的输出"},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "completion_tokens_details": {"reasoning_tokens": 1000},
            },
        }
        with mock.patch("generate_figures.requests.post") as mock_post:
            mock_post.return_value = mock.MagicMock(
                status_code=200,
                json=lambda: fake_response,
                raise_for_status=lambda: None,
            )
            res = call_llm("some-thinking-model", "sys", "user", log=logging.getLogger())
            self.assertEqual(res["content"], "thinking 后的输出")


class TestValidateProfileSections(unittest.TestCase):
    def test_complete_profile_ok(self):
        ok, missing = validate_profile_sections(SAMPLE_PROFILE_COMPLETE)
        self.assertTrue(ok, f"完整 profile 应 pass, missing={missing}")
        self.assertEqual(missing, [])

    def test_missing_section_fails(self):
        # 删掉 "反差 / 鲜为人知点" section
        incomplete = SAMPLE_PROFILE_COMPLETE.split("## 反差")[0]
        ok, missing = validate_profile_sections(incomplete)
        self.assertFalse(ok)
        self.assertIn("反差 / 鲜为人知点", missing)

    def test_all_8_sections_required(self):
        self.assertEqual(len(PROFILE_SECTIONS_REQUIRED), 8)


class TestMaterialToText(unittest.TestCase):
    def test_all_three_sources(self):
        material = {
            "wiki": "维基内容 X",
            "wikidata": {"label_zh": "Q1", "birth": "100"},
            "history": "二十四史内容 Y",
            "history_page": "三國志/卷35",
        }
        text = material_to_text(material)
        self.assertIn("维基中文", text)
        self.assertIn("维基内容 X", text)
        self.assertIn("Wikidata 字段", text)
        self.assertIn("二十四史本传", text)
        self.assertIn("二十四史内容 Y", text)
        self.assertIn("三國志/卷35", text)

    def test_fallback_no_history(self):
        material = {"wiki": "W", "wikidata": {"a": "b"}, "history": None}
        text = material_to_text(material)
        self.assertIn("维基中文", text)
        self.assertIn("Wikidata 字段", text)
        self.assertNotIn("二十四史本传", text)

    def test_fallback_no_wikidata(self):
        material = {"wiki": "W", "wikidata": None, "history": None}
        text = material_to_text(material)
        self.assertIn("维基中文", text)
        self.assertNotIn("Wikidata 字段", text)


class TestParseJsonSafe(unittest.TestCase):
    def test_plain_json(self):
        s = '{"a": 1, "b": 2}'
        self.assertEqual(parse_json_safe(s), {"a": 1, "b": 2})

    def test_markdown_wrapped(self):
        s = '```json\n{"a": 1}\n```'
        self.assertEqual(parse_json_safe(s), {"a": 1})

    def test_with_prose_prefix(self):
        s = '这是 JSON:\n{"a": 1}'
        # 我的 parse 用 regex 抓首个 {} block
        result = parse_json_safe(s)
        self.assertEqual(result, {"a": 1})


class TestEstimateCostCny(unittest.TestCase):
    def test_deepseek_cheap(self):
        usage = {"prompt_tokens": 10000, "completion_tokens": 2000}
        cost = estimate_cost_cny("deepseek-v3.2", usage)
        # 估算: 10000 * 3.5e-6 + 2000 * 10.5e-6 = 0.035 + 0.021 = 0.056
        self.assertAlmostEqual(cost, 0.056, places=3)

    def test_haiku_more_expensive(self):
        usage = {"prompt_tokens": 10000, "completion_tokens": 2000}
        cost_d = estimate_cost_cny("deepseek-v3.2", usage)
        cost_h = estimate_cost_cny("claude-haiku-4-5-20251001", usage)
        self.assertGreater(cost_h, cost_d, "haiku 应该比 deepseek 贵")

    def test_flash_cheapest(self):
        usage = {"prompt_tokens": 10000, "completion_tokens": 2000}
        cost_f = estimate_cost_cny("gemini-3.1-flash-lite", usage)
        cost_d = estimate_cost_cny("deepseek-v3.2", usage)
        self.assertLess(cost_f, cost_d, "flash 应该比 deepseek 便宜")


class TestCluesFromProfile_BanlistInject(unittest.TestCase):
    """AC18 — clues_from_profile 必须 inject banlist 到 prompt"""

    def test_banlist_injected_in_prompt(self):
        """banlist 应注入 prompt 让 LLM 看到"""
        captured = []

        def fake_post(url, **kwargs):
            payload = kwargs["json"]
            user_content = payload["messages"][-1]["content"]
            captured.append(user_content)
            return mock.MagicMock(
                status_code=200,
                json=lambda: {
                    "choices": [{
                        "message": {"content": json.dumps({
                            "name": "测试", "aliases": ["a", "b"],
                            "clues": [{"text": f"clue{d}" * 5, "difficulty": d} for d in range(1, 8)],
                        })},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                },
                raise_for_status=lambda: None,
            )

        with mock.patch("generate_figures.requests.post", side_effect=fake_post):
            banlist = ["三顾茅庐", "出师表", "木牛流马"]
            clues, _ = clues_from_profile(
                profile_md=SAMPLE_PROFILE_COMPLETE,
                banlist=banlist,
                good_examples=["好示例占位"],
                bad_examples=["坏示例占位"],
                flash_model="fake-flash",
                log=logging.getLogger(),
            )
        # 验证 banlist 出现在 prompt
        prompt = captured[0]
        for ban in banlist:
            self.assertIn(ban, prompt, f"banlist 词 '{ban}' 必须出现在 prompt")
        self.assertIn("BANLIST", prompt)


class TestJudgeRetryLoop(unittest.TestCase):
    """T12 — judge 违规自动重试,inject 反馈"""

    def test_retry_on_violation_then_pass(self):
        """第一次 judge 违规, retry 后通过"""
        call_count = [0]

        def fake_post(url, **kwargs):
            call_count[0] += 1
            payload = kwargs["json"]
            user_content = payload["messages"][-1]["content"]
            # 是 clue 生成还是 judge?
            if "JSON schema" in user_content or "BANLIST" in user_content:
                # clue 生成
                resp_content = json.dumps({
                    "name": "测试", "aliases": ["a"],
                    "clues": [{"text": f"clue{d}" * 5, "difficulty": d} for d in range(1, 8)],
                })
            else:
                # judge response
                if call_count[0] <= 2:
                    # 第 1 次 (call 2) judge 违规
                    resp_content = json.dumps({
                        "verdicts": [
                            {"d": 1, "verdict": "违规", "reason": "含 alias"},
                        ] + [{"d": d, "verdict": "合规", "reason": "OK"} for d in range(2, 8)]
                    })
                else:
                    # 第 2 次 judge 合规
                    resp_content = json.dumps({
                        "verdicts": [{"d": d, "verdict": "合规", "reason": "OK"} for d in range(1, 8)]
                    })
            return mock.MagicMock(
                status_code=200,
                json=lambda: {
                    "choices": [{"message": {"content": resp_content}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                },
                raise_for_status=lambda: None,
            )

        with mock.patch("generate_figures.requests.post", side_effect=fake_post):
            # quality_check 的 judge 也走 LLM, patch 该模块的 requests
            clues, calls, fail = judge_and_retry_loop(
                figure_name="测试", profile_md=SAMPLE_PROFILE_COMPLETE,
                banlist=["三顾茅庐"], good_examples=["g"], bad_examples=["b"],
                flash_model="flash", judge_model="flash",
                max_judge_retries=2, log=logging.getLogger(),
            )
        self.assertIsNone(fail, f"应重试 + 通过, 实际 fail={fail}")
        self.assertIsNotNone(clues)
        # 至少 4 次 call: clue + judge (违规) + retry clue + retry judge (合规)
        self.assertGreaterEqual(call_count[0], 4)

    def test_max_retries_exhausted(self):
        """judge 持续违规 N+1 次 → 标 failed"""

        def fake_post(url, **kwargs):
            payload = kwargs["json"]
            user_content = payload["messages"][-1]["content"]
            if "JSON schema" in user_content or "BANLIST" in user_content:
                resp = json.dumps({
                    "name": "测试", "aliases": ["a"],
                    "clues": [{"text": f"c{d}" * 5, "difficulty": d} for d in range(1, 8)],
                })
            else:
                # judge 一直违规
                resp = json.dumps({
                    "verdicts": [{"d": 1, "verdict": "违规", "reason": "X"}] +
                                [{"d": d, "verdict": "合规", "reason": "OK"} for d in range(2, 8)]
                })
            return mock.MagicMock(
                status_code=200,
                json=lambda: {
                    "choices": [{"message": {"content": resp}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 200},
                },
                raise_for_status=lambda: None,
            )

        with mock.patch("generate_figures.requests.post", side_effect=fake_post):
            clues, calls, fail = judge_and_retry_loop(
                figure_name="测试", profile_md=SAMPLE_PROFILE_COMPLETE,
                banlist=[], good_examples=["g"], bad_examples=["b"],
                flash_model="flash", judge_model="flash",
                max_judge_retries=2, log=logging.getLogger(),
            )
        self.assertIsNotNone(fail, "重试穷尽应返回 fail_reason")
        self.assertIsNone(clues)
        self.assertIn("仍违规", fail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
