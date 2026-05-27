import unittest

from scripts.validate_turtle_intro import validate_turtle_intros


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


if __name__ == "__main__":
    unittest.main()
