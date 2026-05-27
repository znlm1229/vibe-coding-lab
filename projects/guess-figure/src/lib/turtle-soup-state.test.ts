import { describe, expect, it } from "vitest";
import type { Figure } from "$lib/types";
import {
  applyTurtleAnswerResult,
  applyTurtleQuestionResult,
  createTurtleSoupRound,
  getTurtleSoupOpening,
  TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
  TURTLE_SOUP_MAX_QUESTIONS,
} from "./turtle-soup-state";

const figure: Figure = {
  id: "target",
  name: "目标人物",
  aliases: ["目标别名"],
  clues: [
    { text: "普通线索一", difficulty: 1 },
    { text: "普通线索二", difficulty: 2 },
  ],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "https://example.test/target",
};

describe("turtle-soup-state", () => {
  it("首屏 round 对象只包含公开字段，不下发人物答案材料", () => {
    const round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    const serializedRound = JSON.stringify(round);

    expect(round).not.toHaveProperty("figure");
    expect(round).not.toHaveProperty("figure_id");
    expect(serializedRound).not.toContain("target");
    expect(serializedRound).not.toContain("wiki_url");
    expect(serializedRound).not.toContain("aliases");
    expect(serializedRound).not.toContain("clues");
    expect(serializedRound).not.toContain("目标人物");
    expect(serializedRound).not.toContain("目标别名");
    expect(serializedRound).not.toContain("普通线索");
  });

  it("完成后只通过 reveal 字段展示公开答案信息", () => {
    const round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    const won = applyTurtleAnswerResult(round, {
      mode: "standalone",
      correct: true,
      completed: true,
      won: true,
      consumes_answer: true,
      answer_attempts_used: 1,
      answer_attempts_remaining: 2,
      question_count: 0,
      reveal: {
        target_name: "目标人物",
        target_aliases: ["目标别名"],
        target_wiki_url: "https://example.test/target",
      },
    });

    expect(won.status).toBe("won");
    expect(won.reveal).toEqual({
      target_name: "目标人物",
      target_aliases: ["目标别名"],
      target_wiki_url: "https://example.test/target",
    });
    expect(JSON.stringify(round)).not.toContain("目标人物");
  });
  it("首屏只暴露 turtle_intro，不暴露人物姓名、别名或普通线索", () => {
    const round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    const opening = getTurtleSoupOpening(round);
    const visibleText = JSON.stringify(opening);

    expect(opening).toEqual({
      turtle_intro: "半盏微光",
      question_limit: TURTLE_SOUP_MAX_QUESTIONS,
      answer_limit: TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
    });
    expect(visibleText).not.toContain("目标人物");
    expect(visibleText).not.toContain("目标别名");
    expect(visibleText).not.toContain("普通线索");
  });

  it("有效问题最多消耗 15 次，invalid 和 degraded 不扣次数", () => {
    let round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    round = applyTurtleQuestionResult(round, "他是不是皇帝？", {
      invalid: true,
      consumes_question: false,
      reason: "请提出能用是/否回答的问题",
    });
    round = applyTurtleQuestionResult(round, "他是不是诗人？", {
      answer: "无关",
      degraded: true,
      consumes_question: false,
    });

    expect(round.question_count).toBe(0);
    expect(round.can_ask_question).toBe(true);

    for (let index = 0; index < TURTLE_SOUP_MAX_QUESTIONS + 1; index += 1) {
      round = applyTurtleQuestionResult(round, `有效问题 ${index + 1}`, {
        answer: "否",
        consumes_question: true,
      });
    }

    expect(round.question_count).toBe(TURTLE_SOUP_MAX_QUESTIONS);
    expect(round.can_ask_question).toBe(false);
    expect(round.questions.filter((item) => item.consumes_question)).toHaveLength(
      TURTLE_SOUP_MAX_QUESTIONS,
    );
  });

  it("最多 3 次答案提交，错答只扣答案次数不扣 question_count", () => {
    let round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    round = applyTurtleQuestionResult(round, "他是不是皇帝？", {
      answer: "否",
      consumes_question: true,
    });
    round = applyTurtleAnswerResult(round, {
      mode: "standalone",
      correct: false,
      completed: false,
      won: false,
      consumes_answer: true,
      answer_attempts_used: 1,
      answer_attempts_remaining: 2,
      question_count: 1,
    });
    round = applyTurtleAnswerResult(round, {
      mode: "standalone",
      correct: false,
      completed: false,
      won: false,
      consumes_answer: true,
      answer_attempts_used: 2,
      answer_attempts_remaining: 1,
      question_count: 1,
    });
    round = applyTurtleAnswerResult(round, {
      mode: "standalone",
      correct: false,
      completed: true,
      won: false,
      consumes_answer: true,
      answer_attempts_used: 3,
      answer_attempts_remaining: 0,
      question_count: 1,
    });

    expect(round.question_count).toBe(1);
    expect(round.answer_attempts_used).toBe(3);
    expect(round.can_submit_answer).toBe(false);
    expect(round.status).toBe("lost");
    expect(round.revealed).toBe(true);
  });

  it("猜中后立即胜利并停止继续提交答案", () => {
    const round = createTurtleSoupRound({
      figures: [figure],
      intros: { 目标人物: "半盏微光" },
      createSessionId: () => "session-1",
    });

    const won = applyTurtleAnswerResult(round, {
      mode: "standalone",
      correct: true,
      completed: true,
      won: true,
      consumes_answer: true,
      answer_attempts_used: 1,
      answer_attempts_remaining: 2,
      question_count: 0,
    });

    expect(won.status).toBe("won");
    expect(won.can_submit_answer).toBe(false);
    expect(won.revealed).toBe(true);
  });
});
