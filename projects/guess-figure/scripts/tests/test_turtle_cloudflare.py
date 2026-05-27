import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.turtle_cloudflare import (
    CloudflareIngestConfig,
    CommandFailure,
    ingest_corpus_to_cloudflare,
)
from scripts.turtle_corpus import build_sample_corpus


def make_text(length: int) -> str:
    unit = "春秋战国秦汉三国两晋南北朝隋唐宋元明清。"
    return (unit * ((length // len(unit)) + 1))[:length]


class FakeRunner:
    def __init__(self, fail_step: str | None = None):
        self.commands: list[list[str]] = []
        self.fail_step = fail_step

    def __call__(self, command: list[str], cwd: Path | None = None):
        self.commands.append(command)
        joined = " ".join(command)
        if self.fail_step and self.fail_step in joined:
            raise CommandFailure(command, "模拟 wrangler 失败", returncode=1)
        return None


class TurtleCloudflareTest(unittest.TestCase):
    def build_sample(self, output_dir: Path):
        return build_sample_corpus(
            output_dir=output_dir,
            figures=[
                {
                    "id": "诸葛亮",
                    "name": "诸葛亮",
                    "aliases": ["孔明"],
                    "wiki_url": "https://zh.wikipedia.org/wiki/诸葛亮",
                    "wikisource_page": "三国志/卷35",
                    "clues": [{"text": make_text(300)}],
                }
            ],
            profiles={"诸葛亮": make_text(900)},
            sample_size=1,
        )

    def test_ingest_uploads_r2_upserts_vectorize_and_writes_d1_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_result = self.build_sample(output_dir)
            runner = FakeRunner()

            summary = ingest_corpus_to_cloudflare(
                build_result.report,
                output_dir=output_dir,
                config=CloudflareIngestConfig(
                    bucket="guess-figure-turtle-corpus",
                    vectorize_index="guess-figure-turtle-rag",
                    d1_database="guess-figure-db",
                    mock_embedding=True,
                ),
                command_runner=runner,
            )

            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(summary["completed_steps"], ["r2_upload", "vectorize_upsert", "d1_manifest"])
            self.assertEqual(summary["vector_dimensions"], 1024)
            self.assertTrue(summary["r2_keys"]["chunks_jsonl"].startswith("turtle-corpus-v1/"))
            self.assertTrue(summary["r2_keys"]["build_report"].startswith("turtle-corpus-v1/"))

            commands = [" ".join(command) for command in runner.commands]
            self.assertTrue(any("r2 object put guess-figure-turtle-corpus/" in item for item in commands))
            self.assertTrue(any("vectorize upsert guess-figure-turtle-rag" in item for item in commands))
            self.assertTrue(any("d1 execute guess-figure-db --remote --command" in item for item in commands))

            upsert_rows = [
                json.loads(line)
                for line in Path(summary["vectorize_file"]).read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(upsert_rows), build_result.report["chunk_count"])
            self.assertTrue(all(len(row["values"]) == 1024 for row in upsert_rows))
            self.assertTrue(all(row["metadata"]["embedding_model"] == "@cf/qwen/qwen3-embedding-0.6b" for row in upsert_rows))
            self.assertTrue(all(row["metadata"]["vector_dimensions"] == 1024 for row in upsert_rows))

    def test_failure_writes_resume_checkpoint_and_failed_source_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_result = self.build_sample(output_dir)
            runner = FakeRunner(fail_step="vectorize upsert")

            with self.assertRaises(CommandFailure):
                ingest_corpus_to_cloudflare(
                    build_result.report,
                    output_dir=output_dir,
                    config=CloudflareIngestConfig(
                        bucket="guess-figure-turtle-corpus",
                        vectorize_index="guess-figure-turtle-rag",
                        d1_database="guess-figure-db",
                        mock_embedding=True,
                    ),
                    command_runner=runner,
                )

            checkpoint = json.loads((output_dir / "cloud-checkpoint.json").read_text(encoding="utf-8"))
            failed_sources = json.loads((output_dir / "failed-sources.json").read_text(encoding="utf-8"))

            self.assertEqual(checkpoint["completed_steps"], ["r2_upload"])
            self.assertEqual(checkpoint["failed_step"], "vectorize_upsert")
            self.assertIn("--cloud", checkpoint["resume_command"])
            self.assertIn("r2_keys", checkpoint)
            self.assertEqual(failed_sources["failed_step"], "vectorize_upsert")
            self.assertEqual(failed_sources["source_counts"], build_result.report["source_counts"])

    def test_cli_sample_cloud_uses_wrangler_runner_and_can_fail_with_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_turtle_corpus.py",
                    "--sample",
                    "--cloud",
                    "--output",
                    str(output_dir),
                    "--mock-embedding",
                    "--wrangler-bin",
                    sys.executable,
                ],
                cwd=Path.cwd(),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((output_dir / "cloud-checkpoint.json").exists())


if __name__ == "__main__":
    unittest.main()
