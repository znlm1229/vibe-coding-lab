import { describe, expect, it } from "vitest";
import { normalizeQuestion, validateTurtleQuestion } from "./turtle-question";

describe("normalizeQuestion", () => {
  it("去首尾空白、合并中间空白，并统一中英文问号", () => {
    expect(normalizeQuestion("  他   是否\t当过 皇帝?  ")).toBe("他 是否 当过 皇帝？");
  });

  it("多个问号统一成一个中文问号", () => {
    expect(normalizeQuestion("他有别名吗？？")).toBe("他有别名吗？");
  });
});

describe("validateTurtleQuestion", () => {
  it.each(["他是不是诸葛亮？", "他是否当过皇帝？", "他有别名吗？", "他姓刘吗？"])(
    "接受合法 yes/no 问法：%s",
    (question) => {
      expect(validateTurtleQuestion(question)).toEqual({
        valid: true,
        normalizedQuestion: normalizeQuestion(question),
        consumesQuestion: true,
      });
    },
  );

  it.each(["他是不是诸葛亮？", "他姓刘吗？", "他有别名吗？"])(
    "直接猜名/姓氏/别名 yes/no 问题不被拦截：%s",
    (question) => {
      expect(validateTurtleQuestion(question).valid).toBe(true);
    },
  );

  it.each(["他是谁？", "介绍一下他"])("非 yes/no 问法返回 invalid 且不消耗次数：%s", (question) => {
    expect(validateTurtleQuestion(question)).toEqual({
      valid: false,
      normalizedQuestion: normalizeQuestion(question),
      consumesQuestion: false,
      reason: "invalid-question",
    });
  });
});
