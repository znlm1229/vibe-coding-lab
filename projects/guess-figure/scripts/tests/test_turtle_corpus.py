import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.turtle_corpus import (
    CorpusSource,
    build_sample_corpus,
    build_corpus_from_sources,
    chunk_text,
    metadata_size_bytes,
    write_corpus_outputs,
)
from scripts.turtle_history import HistoryPage, build_history_batch


def make_text(length: int) -> str:
    unit = "春秋战国秦汉三国两晋南北朝隋唐宋元明清。"
    return (unit * ((length // len(unit)) + 1))[:length]


def assert_full_coverage(test_case: unittest.TestCase, text_length: int) -> None:
    chunks = chunk_text(make_text(text_length), chunk_size=700, overlap=100)
    covered = [False] * text_length
    for chunk in chunks:
        test_case.assertGreaterEqual(len(chunk.text), 500)
        test_case.assertLessEqual(len(chunk.text), 800)
        for index in range(chunk.start, chunk.end):
            covered[index] = True

    missing = [index for index, is_covered in enumerate(covered) if not is_covered]
    test_case.assertEqual(missing, [], f"{text_length} 字文本存在未覆盖位置")


class TurtleCorpusTest(unittest.TestCase):
    def test_chunk_text_uses_target_size_and_overlap(self):
        chunks = chunk_text(make_text(1900), chunk_size=700, overlap=100)

        self.assertEqual([len(chunk.text) for chunk in chunks], [700, 700, 700])
        self.assertTrue(all(500 <= len(chunk.text) <= 800 for chunk in chunks))
        self.assertEqual(chunks[0].end - chunks[1].start, 100)
        self.assertEqual(chunks[1].end - chunks[2].start, 100)

    def test_chunk_text_covers_tail_boundary_lengths(self):
        for text_length in (1099, 1200, 1401):
            with self.subTest(text_length=text_length):
                assert_full_coverage(self, text_length)

    def test_chunk_metadata_stays_under_10k(self):
        metadata = {
            "chunk_id": "profile-001",
            "source_type": "profile",
            "source_id": "profiles/诸葛亮.md",
            "figure_id": "诸葛亮",
            "figure_name": "诸葛亮",
            "title": "诸葛亮人物档案",
            "start": 0,
            "end": 700,
            "source_url": "https://example.test/zh/诸葛亮",
        }

        self.assertLess(metadata_size_bytes(metadata), 10 * 1024)

    def test_sample_build_report_contains_required_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_sample_corpus(
                output_dir=Path(temp_dir),
                figures=[
                    {
                        "id": "诸葛亮",
                        "name": "诸葛亮",
                        "aliases": ["孔明"],
                        "wiki_url": "https://zh.wikipedia.org/wiki/诸葛亮",
                        "wikisource_page": "三国志/卷35",
                        "clues": [{"text": make_text(260)}],
                    }
                ],
                profiles={"诸葛亮": make_text(900)},
                sample_size=1,
            )

            report = result.report
            self.assertEqual(report["corpus_version"], "turtle-corpus-v1")
            self.assertEqual(report["index_version"], "turtle-rag-index-v1")
            self.assertEqual(report["source_counts"]["profile"], 1)
            self.assertEqual(report["source_counts"]["wikipedia"], 1)
            self.assertEqual(report["source_counts"]["wikisource"], 1)
            self.assertGreater(report["chunk_count"], 0)
            self.assertEqual(report["failures"], [])
            self.assertIn("chunks_jsonl", report["output_files"])
            self.assertIn("report_json", report["output_files"])

            chunk_path = Path(report["output_files"]["chunks_jsonl"])
            rows = [json.loads(line) for line in chunk_path.read_text(encoding="utf-8").splitlines()]
            source_types = {row["metadata"]["source_type"] for row in rows}
            self.assertEqual(source_types, {"profile", "wikipedia", "wikisource"})
            self.assertTrue(all(500 <= len(row["text"]) <= 800 for row in rows))
            self.assertTrue(all(metadata_size_bytes(row["metadata"]) < 10 * 1024 for row in rows))

    def test_write_outputs_creates_report_and_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_sample_corpus(
                output_dir=Path(temp_dir),
                figures=[
                    {
                        "id": "关羽",
                        "name": "关羽",
                        "wiki_url": "https://zh.wikipedia.org/wiki/关羽",
                        "wikisource_page": "三国志/卷36",
                        "clues": [{"text": make_text(300)}],
                    }
                ],
                profiles={"关羽": make_text(850)},
                sample_size=1,
            )
            report_path, chunks_path = write_corpus_outputs(result)

            self.assertTrue(report_path.exists())
            self.assertTrue(chunks_path.exists())
            self.assertGreater(chunks_path.stat().st_size, 0)

    def test_cli_rejects_output_inside_project_root(self):
        project_root = Path.cwd()
        output_dir = project_root / "turtle-corpus-output-should-reject"
        if output_dir.exists():
            shutil.rmtree(output_dir)

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_turtle_corpus.py",
                    "--sample",
                    "--output",
                    str(output_dir),
                ],
                cwd=project_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output", result.stderr.lower())
            self.assertFalse(output_dir.exists())
        finally:
            if output_dir.exists():
                shutil.rmtree(output_dir)

    def test_full_build_report_contains_history_book_processed_failed_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sources = [
                CorpusSource(
                    source_type="wikisource",
                    source_id="史記/卷001",
                    title="史記 卷001",
                    text=make_text(900),
                    source_url="https://zh.wikisource.org/wiki/史記/卷001",
                    book="史記",
                    volume="卷001",
                    source_ref="史記/卷001",
                ),
                CorpusSource(
                    source_type="wikisource",
                    source_id="漢書/卷001",
                    title="漢書 卷001",
                    text=make_text(900),
                    source_url="https://zh.wikisource.org/wiki/漢書/卷001",
                    book="漢書",
                    volume="卷001",
                    source_ref="漢書/卷001",
                ),
            ]
            failures = [
                {
                    "source_type": "wikisource",
                    "source_id": "三國志/卷001",
                    "title": "三國志 卷001",
                    "book": "三國志",
                    "volume": "卷001",
                    "reason": "fetch_failed",
                    "error": "模拟抓取失败",
                }
            ]

            result = build_corpus_from_sources(
                output_dir=Path(temp_dir),
                sources=sources,
                failures=failures,
                history_book_names=["史記", "漢書", "三國志"],
                budget_report={"token_budget_limit": 10_000, "token_budget_used": 1_800},
            )

            stats = {item["book"]: item for item in result.report["history_book_stats"]}
            self.assertEqual(stats["史記"]["source_processed"], 1)
            self.assertEqual(stats["漢書"]["source_processed"], 1)
            self.assertEqual(stats["三國志"]["source_failed"], 1)
            self.assertIn("processed", stats["史記"])
            self.assertIn("failed", stats["史記"])
            self.assertEqual(result.report["budget"]["token_budget_used"], 1_800)

            rows = [
                json.loads(line)
                for line in Path(result.report["output_files"]["chunks_jsonl"]).read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(all(row["metadata"]["book"] in {"史記", "漢書"} for row in rows))
            self.assertTrue(all("volume" in row["metadata"] for row in rows))

    def test_history_batch_respects_token_and_vector_budget(self):
        pages = [
            HistoryPage(book="史記", title="史記/卷001", volume="卷001"),
            HistoryPage(book="史記", title="史記/卷002", volume="卷002"),
            HistoryPage(book="漢書", title="漢書/卷001", volume="卷001"),
        ]
        texts = {
            "史記/卷001": make_text(900),
            "史記/卷002": make_text(900),
            "漢書/卷001": make_text(900),
        }

        batch = build_history_batch(
            pages=pages,
            fetch_text=lambda title: texts[title],
            token_budget=1_500,
            vector_budget=3,
        )

        self.assertEqual([source.source_id for source in batch.sources], ["史記/卷001"])
        self.assertTrue(batch.budget["budget_exhausted"])
        self.assertEqual(batch.budget["next_resume_after"], "史記/卷001")
        self.assertGreater(batch.budget["token_budget_used"], 0)

    def test_history_batch_marks_single_source_over_budget_as_failed(self):
        pages = [
            HistoryPage(book="史記", title="史記/卷001", volume="卷001"),
            HistoryPage(book="史記", title="史記/卷002", volume="卷002"),
        ]
        texts = {
            "史記/卷001": make_text(2_000),
            "史記/卷002": make_text(700),
        }

        batch = build_history_batch(
            pages=pages,
            fetch_text=lambda title: texts[title],
            token_budget=800,
            vector_budget=2,
        )

        self.assertEqual([source.source_id for source in batch.sources], ["史記/卷002"])
        self.assertEqual(batch.budget["failed_pages"], 1)
        self.assertEqual(batch.failures[0]["source_id"], "史記/卷001")
        self.assertEqual(batch.failures[0]["reason"], "source_over_budget")
        self.assertEqual(batch.budget["next_resume_after"], "史記/卷002")


if __name__ == "__main__":
    unittest.main()
