import type {
  Figure,
  TurtleAnswerApiResponse,
  TurtleAnswerReveal,
  TurtleQuestionApiResponse,
} from "$lib/types";

export const TURTLE_SOUP_MAX_QUESTIONS = 15;
export const TURTLE_SOUP_MAX_ANSWER_ATTEMPTS = 3;

export type TurtleSoupStatus = "playing" | "won" | "lost";

export interface TurtleSoupQuestionEntry {
  question: string;
  answer?: string;
  invalid?: boolean;
  degraded?: boolean;
  consumes_question: boolean;
  reason?: string;
}

export interface TurtleSoupRound {
  session_id: string;
  turtle_intro: string;
  question_limit: number;
  answer_limit: number;
  question_count: number;
  answer_attempts_used: number;
  status: TurtleSoupStatus;
  revealed: boolean;
  reveal?: TurtleAnswerReveal;
  questions: TurtleSoupQuestionEntry[];
  can_ask_question: boolean;
  can_submit_answer: boolean;
}

export function createTurtleSoupRound(input: {
  figures: Figure[];
  intros: Record<string, string>;
  createSessionId: () => string;
  random?: () => number;
}): TurtleSoupRound {
  const candidates = input.figures.filter((figure) => input.intros[figure.name]);
  const pool = candidates.length > 0 ? candidates : input.figures;
  if (pool.length === 0) {
    throw new Error("海龟汤题库为空");
  }

  const random = input.random ?? Math.random;
  const index = Math.min(pool.length - 1, Math.floor(random() * pool.length));
  const figure = pool[index];

  return createPublicTurtleSoupRound({
    session_id: input.createSessionId(),
    turtle_intro: input.intros[figure.name] ?? "一处微光未明",
    question_count: 0,
    answer_attempts_used: 0,
    status: "playing",
    questions: [],
  });
}

export function createPublicTurtleSoupRound(input: {
  session_id: string;
  turtle_intro: string;
  question_count?: number;
  answer_attempts_used?: number;
  status?: TurtleSoupStatus;
  questions?: TurtleSoupQuestionEntry[];
  reveal?: TurtleAnswerReveal;
}): TurtleSoupRound {
  const status = input.status ?? "playing";
  return normalizeRound({
    session_id: input.session_id,
    turtle_intro: input.turtle_intro,
    question_limit: TURTLE_SOUP_MAX_QUESTIONS,
    answer_limit: TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
    question_count: input.question_count ?? 0,
    answer_attempts_used: input.answer_attempts_used ?? 0,
    status,
    revealed: status !== "playing",
    reveal: input.reveal,
    questions: input.questions ?? [],
    can_ask_question: true,
    can_submit_answer: true,
  });
}

export function getTurtleSoupOpening(round: TurtleSoupRound): {
  turtle_intro: string;
  question_limit: number;
  answer_limit: number;
} {
  return {
    turtle_intro: round.turtle_intro,
    question_limit: round.question_limit,
    answer_limit: round.answer_limit,
  };
}

export function applyTurtleQuestionResult(
  round: TurtleSoupRound,
  question: string,
  response: TurtleQuestionApiResponse,
): TurtleSoupRound {
  if (round.status !== "playing") return round;

  const consumesQuestion = Boolean(response.consumes_question);
  const serverQuestionCount = response.question_count;
  const nextQuestionCount =
    typeof serverQuestionCount === "number"
      ? serverQuestionCount
      : consumesQuestion
        ? Math.min(TURTLE_SOUP_MAX_QUESTIONS, round.question_count + 1)
        : round.question_count;

  const shouldRecord = !consumesQuestion || round.question_count < TURTLE_SOUP_MAX_QUESTIONS;
  const questions = shouldRecord
    ? [
        ...round.questions,
        {
          question,
          answer: response.answer,
          invalid: response.invalid,
          degraded: response.degraded,
          consumes_question: consumesQuestion,
          reason: response.reason,
        },
      ]
    : round.questions;

  return normalizeRound({
    ...round,
    question_count: nextQuestionCount,
    questions,
  });
}

export function applyTurtleAnswerResult(
  round: TurtleSoupRound,
  response: TurtleAnswerApiResponse,
): TurtleSoupRound {
  if (round.status !== "playing") return round;

  const attemptsUsed =
    response.answer_attempts_used ??
    (response.consumes_answer
      ? Math.min(TURTLE_SOUP_MAX_ANSWER_ATTEMPTS, round.answer_attempts_used + 1)
      : round.answer_attempts_used);
  const questionCount = Math.max(round.question_count, response.question_count ?? 0);
  const won = Boolean(response.correct && response.won);
  const lost = Boolean(response.completed && !response.won);
  const status = won ? "won" : lost ? "lost" : "playing";

  return normalizeRound({
    ...round,
    question_count: questionCount,
    answer_attempts_used: Math.min(TURTLE_SOUP_MAX_ANSWER_ATTEMPTS, attemptsUsed),
    status,
    revealed: status !== "playing",
    reveal: status === "playing" ? undefined : response.reveal,
  });
}

function normalizeRound(round: TurtleSoupRound): TurtleSoupRound {
  const active = round.status === "playing";
  const questionCount = Math.min(
    TURTLE_SOUP_MAX_QUESTIONS,
    Math.max(0, round.question_count),
  );
  const answerAttemptsUsed = Math.min(
    TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
    Math.max(0, round.answer_attempts_used),
  );

  return {
    ...round,
    question_limit: TURTLE_SOUP_MAX_QUESTIONS,
    answer_limit: TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
    question_count: questionCount,
    answer_attempts_used: answerAttemptsUsed,
    revealed: round.revealed || round.status !== "playing",
    can_ask_question: active && questionCount < TURTLE_SOUP_MAX_QUESTIONS,
    can_submit_answer: active && answerAttemptsUsed < TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
  };
}
