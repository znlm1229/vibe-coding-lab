import { buildTurtleJudgePrompt, TURTLE_JUDGE_SYSTEM_PROMPT } from "./turtle-prompts";

export const RAG_EMBEDDING_MODEL = "@cf/qwen/qwen3-embedding-0.6b";
export const RAG_RERANKER_MODEL = "@cf/baai/bge-reranker-base";
export const DEFAULT_TURTLE_JUDGE_MODEL = "@cf/meta/llama-3.1-8b-instruct";

export type TurtleRagAnswer = "是" | "否" | "无关";

export interface TurtleTargetFigure {
  id: string;
  name: string;
  aliases: string[];
}

export interface TurtleChunkMetadata {
  chunk_id: string;
  source_type: string;
  source_id: string;
  title: string;
  start: number;
  end: number;
  figure_id?: string;
  figure_name?: string;
  source_url?: string;
  text?: string;
  content?: string;
  snippet?: string;
}

export interface TurtleVectorMatch {
  id?: string;
  score?: number;
  metadata: TurtleChunkMetadata;
}

export interface TurtleEvidenceChunk {
  id: string;
  score?: number;
  rerankScore?: number;
  metadata: TurtleChunkMetadata;
  text: string;
}

export interface TurtleRagDependencies {
  ai: {
    run(model: string, input: unknown): Promise<unknown>;
  };
  vectorize: {
    query(vector: number[], options: unknown): Promise<{ matches?: TurtleVectorMatch[] }>;
  };
  judgeModel?: string;
}

export interface AnswerTurtleQuestionInput {
  targetFigure: TurtleTargetFigure;
  normalizedQuestion: string;
  ragIndexVersion: string;
  promptVersion: string;
  dependencies: TurtleRagDependencies;
}

export interface TurtleRagResult {
  answer: TurtleRagAnswer;
  evidence: TurtleEvidenceChunk[];
  degraded: boolean;
  ragIndexVersion: string;
  promptVersion: string;
}

export async function answerTurtleQuestion(input: AnswerTurtleQuestionInput): Promise<TurtleRagResult> {
  const expandedQuery = buildExpandedQuery(input.targetFigure, input.normalizedQuestion);

  try {
    const embeddingResponse = await input.dependencies.ai.run(RAG_EMBEDDING_MODEL, {
      text: expandedQuery,
    });
    const vector = extractEmbedding(embeddingResponse);
    if (!vector) {
      return degradedResult(input, []);
    }

    const vectorResponse = await input.dependencies.vectorize.query(vector, {
      topK: 20,
      returnMetadata: true,
    });
    const matches = vectorResponse.matches ?? [];
    if (matches.length < 4) {
      return degradedResult(input, matches.map(toEvidenceChunk));
    }

    const reranked = await rerankEvidence(input.dependencies, expandedQuery, matches);
    const evidence = reranked.slice(0, clampEvidenceCount(reranked.length));
    if (evidence.length < 4) {
      return degradedResult(input, evidence);
    }

    const prompt = buildTurtleJudgePrompt({
      targetFigure: input.targetFigure,
      normalizedQuestion: input.normalizedQuestion,
      evidence,
    });
    const judgeResponse = await input.dependencies.ai.run(
      input.dependencies.judgeModel ?? DEFAULT_TURTLE_JUDGE_MODEL,
      {
        messages: [
          { role: "system", content: TURTLE_JUDGE_SYSTEM_PROMPT },
          { role: "user", content: prompt },
        ],
        max_tokens: 64,
      },
    );
    const parsedJudge = parseTurtleJudgeAnswerWithValidity(extractAiText(judgeResponse));

    return {
      answer: parsedJudge.answer,
      evidence,
      degraded: !parsedJudge.valid,
      ragIndexVersion: input.ragIndexVersion,
      promptVersion: input.promptVersion,
    };
  } catch (e) {
    console.warn("[turtle-rag] answer failed:", e);
    return degradedResult(input, []);
  }
}

export function buildExpandedQuery(targetFigure: TurtleTargetFigure, normalizedQuestion: string): string {
  const aliases = targetFigure.aliases.filter(Boolean).join(" ");
  return [targetFigure.name, aliases, normalizedQuestion].filter(Boolean).join(" ");
}

export function parseTurtleJudgeAnswer(raw: unknown): TurtleRagAnswer {
  return parseTurtleJudgeAnswerWithValidity(raw).answer;
}

function parseTurtleJudgeAnswerWithValidity(raw: unknown): { answer: TurtleRagAnswer; valid: boolean } {
  const text = String(raw ?? "").trim();
  const unwrapped = unwrapMarkdownJson(text);
  const parsed = parseJsonObject(unwrapped);
  const answer =
    parsed && typeof parsed === "object" && "answer" in parsed
      ? (parsed as { answer?: unknown }).answer
      : unwrapped;

  if (isTurtleAnswer(answer)) return { answer, valid: true };
  return { answer: "无关", valid: false };
}

async function rerankEvidence(
  dependencies: TurtleRagDependencies,
  expandedQuery: string,
  matches: TurtleVectorMatch[],
): Promise<TurtleEvidenceChunk[]> {
  const evidence = matches.map(toEvidenceChunk);
  const response = await dependencies.ai.run(RAG_RERANKER_MODEL, {
    query: expandedQuery,
    documents: evidence.map((chunk) => chunk.text),
  });
  const scores = extractRerankScores(response);
  if (scores.length === 0) return evidence;

  const reranked = scores
    .filter((item) => item.index >= 0 && item.index < evidence.length)
    .sort((a, b) => b.score - a.score)
    .map((item) => ({
      ...evidence[item.index],
      rerankScore: item.score,
    }));
  const rerankedIds = new Set(reranked.map((chunk) => chunk.id));
  return [
    ...reranked,
    ...evidence.filter((chunk) => !rerankedIds.has(chunk.id)),
  ];
}

function toEvidenceChunk(match: TurtleVectorMatch): TurtleEvidenceChunk {
  const metadata = match.metadata;
  return {
    id: match.id ?? metadata.chunk_id,
    score: match.score,
    metadata,
    text: metadata.text ?? metadata.content ?? metadata.snippet ?? metadata.title,
  };
}

function clampEvidenceCount(count: number): number {
  return Math.min(6, Math.max(4, Math.min(5, count)));
}

function degradedResult(
  input: Pick<AnswerTurtleQuestionInput, "ragIndexVersion" | "promptVersion">,
  evidence: TurtleEvidenceChunk[],
): TurtleRagResult {
  return {
    answer: "无关",
    evidence,
    degraded: true,
    ragIndexVersion: input.ragIndexVersion,
    promptVersion: input.promptVersion,
  };
}

function extractEmbedding(response: unknown): number[] | null {
  const data = getPath(response, ["data"]);
  if (Array.isArray(data)) {
    const first = data[0] as { embedding?: unknown };
    if (Array.isArray(first?.embedding)) return first.embedding as number[];
  }

  const embedding = getPath(response, ["embedding"]) ?? getPath(response, ["result", "data", 0, "embedding"]);
  return Array.isArray(embedding) ? (embedding as number[]) : null;
}

function extractRerankScores(response: unknown): Array<{ index: number; score: number }> {
  const candidates =
    getPath(response, ["response"]) ??
    getPath(response, ["data"]) ??
    getPath(response, ["result"]) ??
    response;
  if (!Array.isArray(candidates)) return [];

  return candidates
    .map((item, fallbackIndex) => {
      const candidate = item as { index?: unknown; score?: unknown; relevance_score?: unknown };
      const index = Number(candidate.index ?? fallbackIndex);
      const score = Number(candidate.score ?? candidate.relevance_score ?? 0);
      return { index, score };
    })
    .filter((item) => Number.isFinite(item.index) && Number.isFinite(item.score));
}

function extractAiText(response: unknown): string {
  if (typeof response === "string") return response;

  const direct =
    getPath(response, ["response"]) ??
    getPath(response, ["result"]) ??
    getPath(response, ["output_text"]) ??
    getPath(response, ["choices", 0, "message", "content"]);

  if (typeof direct === "string") return direct;
  return JSON.stringify(response ?? "");
}

function unwrapMarkdownJson(text: string): string {
  const fence = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return (fence?.[1] ?? text).trim();
}

function parseJsonObject(text: string): unknown {
  const direct = safeJsonParse(text);
  if (direct) return direct;

  const embeddedJson = text.match(/\{[\s\S]*\}/)?.[0];
  return embeddedJson ? safeJsonParse(embeddedJson) : null;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isTurtleAnswer(value: unknown): value is TurtleRagAnswer {
  return value === "是" || value === "否" || value === "无关";
}

function getPath(value: unknown, path: Array<string | number>): unknown {
  let cursor = value as Record<string, unknown> | unknown[];
  for (const part of path) {
    if (cursor == null || typeof cursor !== "object") return undefined;
    cursor = (cursor as Record<string | number, unknown>)[part] as Record<string, unknown> | unknown[];
  }
  return cursor;
}
