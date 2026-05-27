// 题库 figure 类型（跟 figures.json schema 对齐）

export interface Clue {
  text: string;
  difficulty: number; // 1-7
}

export interface Figure {
  id: string;
  name: string;
  aliases: string[];
  clues: Clue[]; // 7 条，按难度 1-7 排
  source: string;
  wikidata_id: string;
  wiki_url: string;
  _meta?: {
    model?: string;
    generated_at?: string;
    usage?: Record<string, unknown>;
  };
}

export type GameStatus =
  | "playing" // 标准范围内（线索 1-5）
  | "rescue"  // 求救范围内（线索 6-7）
  | "won"     // 猜中
  | "revealed"; // 7 条用完 / 放弃 → 显示答案

export type TurtleQuestionAnswer = "是" | "否" | "无关";

export type TurtleMode = "embedded" | "standalone";

export interface TurtleQuestionApiResponse {
  answer?: TurtleQuestionAnswer;
  invalid?: boolean;
  consumes_question: boolean;
  cached?: boolean;
  degraded?: boolean;
  network_error?: boolean;
  reason?: string;
  mode?: TurtleMode;
  rag_index_version?: string;
  prompt_version?: string;
}
