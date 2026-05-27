import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_turtle_intro import load_json, validate_turtle_intros


REVIEW_FLAGGED_TERMS = ("梦", "歌", "碗", "烟", "棋", "黄", "挑灯", "篱", "铁屋")


def make_figure(figure_id: str = "孔子") -> dict:
    return {
        "id": figure_id,
        "name": figure_id,
        "aliases": ["仲尼", "至圣先师"],
    }


class TurtleIntroValidationTest(unittest.TestCase):
    def test_accepts_short_implicit_intro_for_every_figure(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子"), make_figure("李白")],
            intros={"孔子": "不合时宜的光", "李白": "杯中倒影"},
        )

        self.assertEqual(errors, [])

    def test_rejects_missing_figure_intro(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子"), make_figure("李白")],
            intros={"孔子": "不合时宜的光"},
        )

        self.assertTrue(any("缺少汤面" in error and "李白" in error for error in errors))

    def test_rejects_name_leak(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子")],
            intros={"孔子": "孔子的光"},
        )

        self.assertTrue(any("姓名" in error for error in errors))

    def test_rejects_alias_leak(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子")],
            intros={"孔子": "仲尼门外"},
        )

        self.assertTrue(any("别名" in error for error in errors))

    def test_rejects_overlong_intro(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子")],
            intros={"孔子": "这是一条明显超过十六个中文字的汤面"},
        )

        self.assertTrue(any("长度" in error for error in errors))

    def test_rejects_banned_identifying_terms(self):
        errors = validate_turtle_intros(
            figures=[make_figure("孔子")],
            intros={"孔子": "春秋先生"},
        )

        self.assertTrue(any("禁词" in error for error in errors))
        self.assertFalse(any("先生" in error for error in errors))

    def test_rejects_review_flagged_imagery_terms(self):
        errors = validate_turtle_intros(
            figures=[make_figure("庄子")],
            intros={"庄子": "梦外一息"},
        )

        self.assertTrue(any("强意象" in error for error in errors))

    def test_current_intro_data_avoids_review_flagged_terms(self):
        intros = load_json(ROOT_DIR / "src" / "lib" / "data" / "turtle-intros.json")
        leaked = {
            figure_id: intro
            for figure_id, intro in intros.items()
            if any(term in intro for term in REVIEW_FLAGGED_TERMS)
        }

        self.assertEqual(leaked, {})

    def test_generator_help_runs_when_executed_by_path(self):
        result = subprocess.run(
            [sys.executable, "scripts/generate_turtle_intro.py", "--help"],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
