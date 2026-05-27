import type { TurtleEvidenceChunk, TurtleTargetFigure } from "./turtle-rag";

export const TURTLE_JUDGE_SYSTEM_PROMPT = [
  "你是海龟汤模式的三态裁判。",
  "你只能根据提供的证据判断玩家的问题。",
  "可见答案只能是：是、否、无关。",
  "证据不足、不确定、证据无法直接支持判断、问题和目标人物关系不清时，必须回答无关。",
  "只输出 JSON：{\"answer\":\"是\"}、{\"answer\":\"否\"} 或 {\"answer\":\"无关\"}。",
].join("\n");

export function buildTurtleJudgePrompt(input: {
  targetFigure: TurtleTargetFigure;
  normalizedQuestion: string;
  evidence: TurtleEvidenceChunk[];
}): string {
  const aliases = input.targetFigure.aliases.length > 0 ? input.targetFigure.aliases.join("、") : "无";
  const evidenceText = input.evidence
    .map((chunk, index) =>
      [
        `证据 ${index + 1}`,
        `chunk_id: ${chunk.metadata.chunk_id}`,
        `source_type: ${chunk.metadata.source_type}`,
        `title: ${chunk.metadata.title}`,
        `figure_id: ${chunk.metadata.figure_id ?? ""}`,
        `figure_name: ${chunk.metadata.figure_name ?? ""}`,
        `text: ${chunk.text}`,
      ].join("\n"),
    )
    .join("\n\n");

  return [
    `目标人物：${input.targetFigure.name}`,
    `别名：${aliases}`,
    `玩家问题：${input.normalizedQuestion}`,
    "",
    "证据：",
    evidenceText,
    "",
    "请仅输出 JSON，answer 只能是“是”“否”“无关”。证据不足或不确定必须输出“无关”。",
  ].join("\n");
}
