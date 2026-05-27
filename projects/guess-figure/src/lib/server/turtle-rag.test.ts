import { describe, expect, it } from "vitest";
import {
  RAG_EMBEDDING_MODEL,
  RAG_RERANKER_MODEL,
  answerTurtleQuestion,
  parseTurtleJudgeAnswer,
} from "./turtle-rag";

const guanYu = {
  id: "guan-yu",
  name: "关羽",
  aliases: ["关云长", "关公", "关圣帝君"],
};

function makeChunk(index: number, text: string, figureId = "guan-yu") {
  return {
    id: `chunk-${index}`,
    score: 0.9 - index * 0.01,
    metadata: {
      chunk_id: `chunk-${index}`,
      source_type: index === 1 ? "wikipedia" : "wikisource",
      source_id: `src-${index}`,
      title: index === 1 ? "关羽 - 维基百科" : "三国志",
      start: index * 100,
      end: index * 100 + text.length,
      figure_id: figureId,
      figure_name: figureId === "guan-yu" ? "关羽" : "诸葛亮",
      source_url: "https://example.test/source",
      text,
    },
  };
}

function makeDeps(options?: {
  vectorMatches?: ReturnType<typeof makeChunk>[];
  rerankScores?: number[];
  rerankResponse?: unknown;
  embeddingResponse?: unknown;
  judgeText?: string;
}) {
  const calls: Array<{ model: string; input: unknown }> = [];
  const vectorQueries: Array<{ vector: number[]; options: unknown }> = [];
  const vectorMatches =
    options?.vectorMatches ??
    Array.from({ length: 20 }, (_, i) =>
      makeChunk(i + 1, `证据片段 ${i + 1}：关羽相关史料。`),
    );

  const dependencies = {
    ai: {
      async run(model: string, input: unknown) {
        calls.push({ model, input });
        if (model === RAG_EMBEDDING_MODEL) {
          if (options?.embeddingResponse !== undefined) {
            return options.embeddingResponse;
          }
          return { data: [{ embedding: [0.1, 0.2, 0.3] }] };
        }
        if (model === RAG_RERANKER_MODEL) {
          if (options?.rerankResponse !== undefined) {
            return options.rerankResponse;
          }
          const scores =
            options?.rerankScores ??
            Array.from({ length: vectorMatches.length }, (_, i) => vectorMatches.length - i);
          return {
            response: scores.map((score, index) => ({ index, score })),
          };
        }
        return {
          response: options?.judgeText ?? JSON.stringify({ answer: "无关" }),
        };
      },
    },
    vectorize: {
      async query(vector: number[], options: unknown) {
        vectorQueries.push({ vector, options });
        return { matches: vectorMatches };
      },
    },
    judgeModel: "@cf/meta/llama-3.1-8b-instruct",
  };

  return { dependencies, calls, vectorQueries };
}

describe("answerTurtleQuestion", () => {
  it("检索 query 注入目标人物姓名、别名和用户问题，并用 Vectorize topK=20", async () => {
    const { dependencies, calls, vectorQueries } = makeDeps({ judgeText: '{"answer":"无关"}' });

    await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    const embeddingCall = calls.find((call) => call.model === RAG_EMBEDDING_MODEL);
    expect(embeddingCall?.input).toMatchObject({
      text: expect.stringContaining("关羽"),
    });
    expect(JSON.stringify(embeddingCall?.input)).toContain("关云长");
    expect(JSON.stringify(embeddingCall?.input)).toContain("关公");
    expect(JSON.stringify(embeddingCall?.input)).toContain("他是不是被后世尊为武圣？");
    expect(vectorQueries[0]).toMatchObject({
      vector: [0.1, 0.2, 0.3],
      options: expect.objectContaining({
        topK: 20,
        returnMetadata: true,
      }),
    });
  });

  it("supports Workers AI data matrix embedding response", async () => {
    const { dependencies, vectorQueries } = makeDeps({
      embeddingResponse: { data: [[0.4, 0.5, 0.6]] },
      judgeText: '{"answer":"unknown"}',
    });

    await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "test question",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    expect(vectorQueries[0]?.vector).toEqual([0.4, 0.5, 0.6]);
  });

  it("supports Workers AI result data matrix embedding response", async () => {
    const { dependencies, vectorQueries } = makeDeps({
      embeddingResponse: { result: { data: [[0.7, 0.8, 0.9]] } },
      judgeText: '{"answer":"unknown"}',
    });

    await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "test question",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    expect(vectorQueries[0]?.vector).toEqual([0.7, 0.8, 0.9]);
  });

  it("先取 Vectorize topK 结果，再 rerank，并只把 4-6 个 evidence chunks 喂给裁判", async () => {
    const { dependencies, calls } = makeDeps({
      judgeText: "```json\n{\"answer\":\"是\"}\n```",
      rerankScores: Array.from({ length: 20 }, (_, i) => (i < 7 ? 100 - i : i)),
    });

    const result = await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    const rerankCall = calls.find((call) => call.model === RAG_RERANKER_MODEL);
    expect(rerankCall?.input).toMatchObject({
      query: expect.stringContaining("关羽"),
    });
    expect((rerankCall?.input as { documents: string[] }).documents).toHaveLength(20);

    const judgeCall = calls.find((call) => call.model === "@cf/meta/llama-3.1-8b-instruct");
    const prompt = JSON.stringify(judgeCall?.input);
    const evidenceCount = (prompt.match(/chunk_id/g) ?? []).length;
    expect(evidenceCount).toBeGreaterThanOrEqual(4);
    expect(evidenceCount).toBeLessThanOrEqual(6);
    expect(result.answer).toBe("是");
    expect(result.evidence).toHaveLength(evidenceCount);
  });

  it("证据不足时返回无关，且不把不确定性猜成否", async () => {
    const { dependencies } = makeDeps({
      vectorMatches: [
        makeChunk(1, "这段只说关羽随刘备起事。"),
        makeChunk(2, "这段只说关羽守荆州。"),
        makeChunk(3, "这段只说关羽谥号。"),
      ],
      judgeText: '{"answer":"否"}',
    });

    const result = await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    expect(result.answer).toBe("无关");
    expect(result.degraded).toBe(true);
  });

  it("关羽武圣维基 fixture 返回是", async () => {
    const wikiFixture = makeChunk(
      1,
      "关羽去世后逐渐被民间神化，又被后世尊称为武圣，与文圣孔子并称。",
    );
    const { dependencies } = makeDeps({
      vectorMatches: [
        wikiFixture,
        makeChunk(2, "关羽字云长，河东解县人。"),
        makeChunk(3, "关羽在民间信仰中又称关公。"),
        makeChunk(4, "后世历代多有追封关羽。"),
        makeChunk(5, "关羽形象见于《三国演义》。"),
        makeChunk(6, "关圣帝君是关羽的神化尊号之一。"),
      ],
      judgeText: '{"answer":"是"}',
    });

    const result = await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    expect(result.answer).toBe("是");
    expect(result.evidence.map((chunk) => chunk.metadata.chunk_id)).toContain("chunk-1");
  });

  it("裁判输出非法答案时降级为无关，不暴露其他可见答案", async () => {
    const { dependencies } = makeDeps({ judgeText: '{"answer":"也许"}' });

    const result = await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    expect(result.answer).toBe("无关");
    expect(result.degraded).toBe(true);
  });

  it("reranker 只返回部分有效分数时，用原 Vectorize 顺序补足证据而不是过早降级", async () => {
    const { dependencies, calls } = makeDeps({
      judgeText: '{"answer":"是"}',
      rerankResponse: {
        response: [
          { index: 0, score: 100 },
          { index: 99, score: 90 },
          { score: "bad" },
        ],
      },
    });

    const result = await answerTurtleQuestion({
      targetFigure: guanYu,
      normalizedQuestion: "他是不是被后世尊为武圣？",
      ragIndexVersion: "rag-v1",
      promptVersion: "prompt-v1",
      dependencies,
    });

    const judgeCall = calls.find((call) => call.model === "@cf/meta/llama-3.1-8b-instruct");
    expect(judgeCall).toBeDefined();
    expect(result.answer).toBe("是");
    expect(result.degraded).toBe(false);
    expect(result.evidence).toHaveLength(5);
    expect(result.evidence.map((chunk) => chunk.metadata.chunk_id)).toEqual([
      "chunk-1",
      "chunk-2",
      "chunk-3",
      "chunk-4",
      "chunk-5",
    ]);
  });
});

describe("parseTurtleJudgeAnswer", () => {
  it.each([
    ['{"answer":"是"}', "是"],
    ["```json\n{\"answer\":\"否\"}\n```", "否"],
    ['答案如下：{"answer":"是"}', "是"],
    ["无关", "无关"],
    ['{"answer":"不确定"}', "无关"],
  ] as const)("容错解析裁判输出 %s", (raw, expected) => {
    expect(parseTurtleJudgeAnswer(raw)).toBe(expected);
  });
});
