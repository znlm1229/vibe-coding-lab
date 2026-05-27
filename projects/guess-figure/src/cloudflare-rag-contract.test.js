// @ts-nocheck
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "..");

function readProjectFile(path) {
  return readFileSync(resolve(root, path), "utf8");
}

describe("004 T1 Cloudflare RAG 契约", () => {
  it("wrangler 声明 Vectorize、R2、AI bindings 与 RAG vars", () => {
    const wrangler = readProjectFile("wrangler.toml");

    expect(wrangler).toContain("[[vectorize]]");
    expect(wrangler).toContain('binding = "GF_VECTORIZE"');
    expect(wrangler).toContain('index_name = "guess-figure-turtle-rag"');

    expect(wrangler).toContain("[[r2_buckets]]");
    expect(wrangler).toContain('binding = "GF_CORPUS_R2"');
    expect(wrangler).toContain('bucket_name = "guess-figure-turtle-corpus"');

    expect(wrangler).toContain("[ai]");
    expect(wrangler).toContain('binding = "AI"');
    expect(wrangler).toContain('RAG_EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b"');
    expect(wrangler).toContain('RAG_INDEX_VERSION = "turtle-rag-v1"');
    expect(wrangler).toContain('RAG_CORPUS_BUCKET = "guess-figure-turtle-corpus"');
    expect(wrangler).toContain('RAG_VECTOR_DIMENSIONS = "1024"');
    expect(wrangler).toContain('RAG_VECTOR_METRIC = "cosine"');
  });

  it("app.d.ts 暴露 RAG runtime binding 类型", () => {
    const appTypes = readProjectFile("src/app.d.ts");

    expect(appTypes).toContain("VectorizeIndex");
    expect(appTypes).toContain("R2Bucket");
    expect(appTypes).toContain("Ai");
    expect(appTypes).toContain("GF_VECTORIZE?: VectorizeIndex");
    expect(appTypes).toContain("GF_CORPUS_R2?: R2Bucket");
    expect(appTypes).toContain("AI?: Ai");
  });

  it("D1 migration 只存 manifest/version/statistics/source records，不存语料全文", () => {
    const migration = readProjectFile("migrations/0002_turtle_rag_manifest.sql");

    expect(migration).toContain("CREATE TABLE IF NOT EXISTS turtle_corpus_versions");
    expect(migration).toContain("CREATE TABLE IF NOT EXISTS turtle_index_versions");
    expect(migration).toContain("CREATE TABLE IF NOT EXISTS turtle_corpus_sources");
    expect(migration).toContain("CREATE TABLE IF NOT EXISTS turtle_build_reports");
    expect(migration).toContain("vector_dimensions INTEGER NOT NULL DEFAULT 1024");
    expect(migration).toContain("vector_metric TEXT NOT NULL DEFAULT 'cosine'");
    expect(migration).toContain("source_type TEXT NOT NULL");
    expect(migration).toContain("r2_object_key TEXT");
    expect(migration).not.toMatch(/\b(full_text|content|body|raw_text|clean_text)\b/i);
  });
});
