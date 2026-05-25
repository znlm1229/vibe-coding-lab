// 002 T14: classifyResult + shouldConsumeClue 单测
//
// 覆盖 06-tasks.md T14 Done when 的 4 case (实际 5 outcome):
//   - correct → 调 markWon, 不消耗
//   - wrong (无 degraded/network_error) → 消耗线索
//   - degraded → 不消耗 (V/X 触发)
//   - network_error → 不消耗 (LLM 失败)
//   - client_error (CheckAnswerError) → 不消耗 (HTTP/network 错)
//
// SPEC AC8 / AC9 / AC22 的核心.

import { describe, it, expect } from "vitest";
import {
  classifyResult,
  shouldConsumeClue,
  type CheckAnswerResult,
  type CheckAnswerError,
} from "./check-answer-client";

describe("classifyResult", () => {
  it("correct: true → kind=correct (含 cached 透传)", () => {
    const r: CheckAnswerResult = { correct: true, reason: "诸葛丞相指诸葛亮", cached: true };
    expect(classifyResult(r)).toEqual({ kind: "correct", reason: "诸葛丞相指诸葛亮", cached: true });
  });

  it("correct: true 无 cached → kind=correct (cached undefined)", () => {
    const r: CheckAnswerResult = { correct: true, reason: "精确匹配" };
    expect(classifyResult(r)).toEqual({ kind: "correct", reason: "精确匹配", cached: undefined });
  });

  it("correct: false, 无 degraded/network_error → kind=wrong", () => {
    const r: CheckAnswerResult = { correct: false, reason: "诸葛梁不是诸葛亮" };
    expect(classifyResult(r)).toEqual({ kind: "wrong", reason: "诸葛梁不是诸葛亮" });
  });

  it("degraded: true → kind=degraded (即使 correct: false 也优先 degraded)", () => {
    const r: CheckAnswerResult = {
      correct: false,
      reason: "今日 AI 裁判额度已用尽，仅接受精确答案",
      degraded: true,
    };
    expect(classifyResult(r)).toEqual({ kind: "degraded", reason: r.reason });
  });

  it("network_error: true → kind=network_error (优先级最高)", () => {
    const r: CheckAnswerResult = {
      correct: false,
      reason: "AI 响应异常，请稍后重试",
      network_error: true,
    };
    expect(classifyResult(r)).toEqual({ kind: "network_error", reason: r.reason });
  });

  it("network_error 与 degraded 同时 true: network_error 优先 (实际不会同时)", () => {
    const r: CheckAnswerResult = {
      correct: false,
      reason: "AI 响应异常",
      network_error: true,
      degraded: true,
    };
    expect(classifyResult(r)).toEqual({ kind: "network_error", reason: r.reason });
  });

  it("CheckAnswerError (client fetch 失败) → kind=client_error", () => {
    const r: CheckAnswerError = { ok: false, error: "网络错误: Failed to fetch" };
    expect(classifyResult(r)).toEqual({ kind: "client_error", reason: r.error });
  });
});

describe("shouldConsumeClue — SPEC G7 仅 wrong 消耗线索", () => {
  it("wrong → true (消耗)", () => {
    expect(shouldConsumeClue({ kind: "wrong", reason: "..." })).toBe(true);
  });

  it("correct → false (不消耗)", () => {
    expect(shouldConsumeClue({ kind: "correct", reason: "..." })).toBe(false);
  });

  it("degraded → false (不消耗, AC9)", () => {
    expect(shouldConsumeClue({ kind: "degraded", reason: "..." })).toBe(false);
  });

  it("network_error → false (不消耗, AC8)", () => {
    expect(shouldConsumeClue({ kind: "network_error", reason: "..." })).toBe(false);
  });

  it("client_error → false (不消耗, 防客户端 / HTTP 错偷线索)", () => {
    expect(shouldConsumeClue({ kind: "client_error", reason: "..." })).toBe(false);
  });
});
