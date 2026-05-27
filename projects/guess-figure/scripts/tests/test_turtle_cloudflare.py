import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.turtle_cloudflare import (
    CloudflareIngestConfig,
    CommandFailure,
    build_wrangler_command,
    ingest_corpus_to_cloudflare,
)
from scripts.turtle_corpus import build_sample_corpus


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
import scripts.build_turtle_corpus as build_cli


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


class FakeRealEmbedder:
    def __init__(self):
        self.calls: list[list[dict]] = []

    def __call__(self, rows: list[dict], config: CloudflareIngestConfig) -> list[list[float]]:
        self.calls.append(rows)
        return [[float((index % 17) / 17) for index in range(config.vector_dimensions)] for _ in rows]


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
            self.assertTrue(summary["r2_keys"]["raw_sources_jsonl"].startswith("turtle-corpus-v1/"))
            self.assertTrue(summary["r2_keys"]["normalized_sources_jsonl"].startswith("turtle-corpus-v1/"))

            commands = [" ".join(command) for command in runner.commands]
            self.assertTrue(any("r2 object put guess-figure-turtle-corpus/" in item for item in commands))
            self.assertTrue(any("sources-raw.jsonl" in item for item in commands))
            self.assertTrue(any("sources-normalized.jsonl" in item for item in commands))
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
            self.assertTrue(Path(summary["source_files"]["raw_sources_jsonl"]).exists())
            self.assertTrue(Path(summary["source_files"]["normalized_sources_jsonl"]).exists())

    def test_non_mock_path_uses_injected_real_embedder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_result = self.build_sample(output_dir)
            runner = FakeRunner()
            embedder = FakeRealEmbedder()

            summary = ingest_corpus_to_cloudflare(
                build_result.report,
                output_dir=output_dir,
                config=CloudflareIngestConfig(
                    bucket="guess-figure-turtle-corpus",
                    vectorize_index="guess-figure-turtle-rag",
                    d1_database="guess-figure-db",
                    mock_embedding=False,
                ),
                command_runner=runner,
                embedder=embedder,
            )

            self.assertEqual(summary["status"], "succeeded")
            self.assertEqual(len(embedder.calls), 1)
            self.assertEqual(len(embedder.calls[0]), build_result.report["chunk_count"])
            upsert_rows = [
                json.loads(line)
                for line in Path(summary["vectorize_file"]).read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(all(len(row["values"]) == 1024 for row in upsert_rows))

    def test_failure_writes_resume_checkpoint_and_failed_source_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "cloud output"
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
            self.assertIn("--cloud", checkpoint["resume_args"])
            self.assertIn(str(output_dir), checkpoint["resume_args"])
            self.assertIn("从头重跑", checkpoint["resume_note"])
            self.assertIn("r2_keys", checkpoint)
            self.assertEqual(failed_sources["failed_step"], "vectorize_upsert")
            self.assertEqual(failed_sources["source_counts"], build_result.report["source_counts"])
            for payload in (checkpoint, failed_sources):
                self.assertEqual(payload["affected_chunk_count"], build_result.report["chunk_count"])
                self.assertGreaterEqual(len(payload["affected_sources"]), 1)
                affected_source = payload["affected_sources"][0]
                self.assertIn("source_type", affected_source)
                self.assertIn("source_id", affected_source)
                self.assertIn("title", affected_source)
                self.assertIn("figure_id", affected_source)
                self.assertGreaterEqual(affected_source["chunk_count"], 1)
                self.assertGreaterEqual(len(affected_source["chunks"]), 1)
                affected_chunk = affected_source["chunks"][0]
                self.assertIn("chunk_id", affected_chunk)
                self.assertIn("start", affected_chunk)
                self.assertIn("end", affected_chunk)

    def test_d1_failure_checkpoint_includes_affected_source_chunk_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_result = self.build_sample(output_dir)
            runner = FakeRunner(fail_step="d1 execute")

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

            self.assertEqual(checkpoint["failed_step"], "d1_manifest")
            self.assertEqual(failed_sources["failed_step"], "d1_manifest")
            for payload in (checkpoint, failed_sources):
                source = payload["affected_sources"][0]
                chunk = source["chunks"][0]
                self.assertIn("chunk_id", chunk)
                self.assertIsInstance(chunk["start"], int)
                self.assertIsInstance(chunk["end"], int)

    def test_wrangler_bin_with_spaces_keeps_executable_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_result = self.build_sample(output_dir)
            runner = FakeRunner()
            wrangler_path = r"C:\Program Files\nodejs\wrangler.cmd"

            ingest_corpus_to_cloudflare(
                build_result.report,
                output_dir=output_dir,
                config=CloudflareIngestConfig(
                    wrangler_bin=wrangler_path,
                    wrangler_args=(),
                    mock_embedding=True,
                ),
                command_runner=runner,
            )

            self.assertGreater(len(runner.commands), 0)
            self.assertTrue(all(command[0] == wrangler_path for command in runner.commands))

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

    def test_cli_cloud_config_requires_explicit_mock_embedding(self):
        config = build_cli.build_cloud_config(
            argparse.Namespace(mock_embedding=False, wrangler_bin=None)
        )

        self.assertFalse(config.mock_embedding)

    def test_default_cli_cloud_config_builds_pnpm_exec_wrangler_argv(self):
        config = build_cli.build_cloud_config(
            argparse.Namespace(mock_embedding=False, wrangler_bin=None)
        )

        command = build_wrangler_command(config, ["r2", "bucket", "list"])

        self.assertEqual(command[:3], ["pnpm", "exec", "wrangler"])
        self.assertEqual(command[3:], ["r2", "bucket", "list"])

    def test_custom_cli_wrangler_bin_with_spaces_does_not_append_default_args(self):
        wrangler_path = r"C:\Program Files\nodejs\wrangler.cmd"
        config = build_cli.build_cloud_config(
            argparse.Namespace(mock_embedding=True, wrangler_bin=wrangler_path)
        )

        command = build_wrangler_command(config, ["vectorize", "list"])

        self.assertEqual(command, [wrangler_path, "vectorize", "list"])


if __name__ == "__main__":
    unittest.main()
