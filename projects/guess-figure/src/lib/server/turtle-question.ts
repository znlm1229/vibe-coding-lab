export type TurtleQuestionValidation =
  | {
      valid: true;
      normalizedQuestion: string;
      consumesQuestion: true;
    }
  | {
      valid: false;
      normalizedQuestion: string;
      consumesQuestion: false;
      reason: "invalid-question";
    };

/**
 * 统一问题文本，供校验和缓存 key 共用。
 *
 * 这里保留词间单个空格，避免把英文、人名或带空格输入粘连成新词。
 */
export function normalizeQuestion(question: string): string {
  const normalized = question
    .trim()
    .replace(/\s+/g, " ")
    .replace(/[?？]+$/g, "？");

  return normalized;
}

/**
 * 只拦截明显不是 yes/no 的问法。
 *
 * 直接猜姓名、姓氏、别名这类问题，只要是 yes/no 形态，就交给后续 RAG/LLM 判定。
 * 返回 consumesQuestion=false 时，调用方应不扣提问次数，也不进入 RAG/LLM。
 */
export function validateTurtleQuestion(question: string): TurtleQuestionValidation {
  const normalizedQuestion = normalizeQuestion(question);
  const compactQuestion = normalizedQuestion.replace(/\s+/g, "");

  if (isYesNoQuestion(compactQuestion)) {
    return {
      valid: true,
      normalizedQuestion,
      consumesQuestion: true,
    };
  }

  return {
    valid: false,
    normalizedQuestion,
    consumesQuestion: false,
    reason: "invalid-question",
  };
}

function isYesNoQuestion(question: string): boolean {
  if (!question) return false;

  return (
    question.includes("是不是") ||
    question.includes("是否") ||
    question.includes("能否") ||
    question.includes("有没有") ||
    question.includes("可否") ||
    /吗？?$/.test(question)
  );
}
