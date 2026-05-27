import json
import tempfile
import unittest
from pathlib import Path

from scripts.turtle_corpus import (
    build_sample_corpus,
    chunk_text,
    metadata_size_bytes,
    write_corpus_outputs,
)


def make_text(length: int) -> str:
    unit = "春秋战国秦汉三国两晋南北朝隋唐宋元明清。"
    return (unit * ((length // len(unit)) + 1))[:length]


class TurtleCorpusTest(unittest.TestCase):
    def test_chunk_text_uses_target_size_and_overlap(self):
        chunks = chunk_text(make_text(1900), chunk_size=700, overlap=100)

        self.assertEqual([len(chunk.text) for chunk in chunks], [700, 700, 700])
        self.assertTrue(all(500 <= len(chunk.text) <= 800 for chunk in chunks))
        self.assertEqual(chunks[0].end - chunks[1].start, 100)
        self.assertEqual(chunks[1].end - chunks[2].start, 100)

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


if __name__ == "__main__":
    unittest.main()
