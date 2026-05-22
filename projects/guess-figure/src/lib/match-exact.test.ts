// 002 T4: match-exact 共享 lib 测试 — 确保 client/server import 同一份代码
//
// 同时 sanity check 现有 normalize + matchExactly 行为不退化 (server 端 pipeline 复用)。
// 测试 case 直接源自 match-exact.ts 的 jsdoc 例子。

import { describe, it, expect } from "vitest";
import { normalize, matchExactly } from "./match-exact";
import type { Figure } from "./types";

const zhugeLiang: Figure = {
  id: "诸葛亮",
  name: "诸葛亮",
  aliases: ["孔明", "卧龙", "武乡侯", "忠武侯"],
  clues: [],
  source: "test",
  wikidata_id: "Q-test",
  wiki_url: "test",
};

describe("normalize", () => {
  it("trim + remove whitespace + remove Chinese punctuation + lowercase", () => {
    expect(normalize("  孔 明！  ")).toBe("孔明");
    expect(normalize("ZhuGe Liang")).toBe("zhugeliang");
    expect(normalize("孔明")).toBe("孔明");
    expect(normalize("")).toBe("");
    expect(normalize("「诸葛亮」")).toBe("诸葛亮");
  });
});

describe("matchExactly", () => {
  it("matches the target's own name", () => {
    expect(matchExactly("诸葛亮", zhugeLiang)).toBe(true);
  });
  it("matches an alias", () => {
    expect(matchExactly("孔明", zhugeLiang)).toBe(true);
  });
  it("matches with leading/trailing whitespace", () => {
    expect(matchExactly("  孔明  ", zhugeLiang)).toBe(true);
  });
  it("matches with embedded whitespace removed", () => {
    expect(matchExactly("孔 明", zhugeLiang)).toBe(true);
  });
  it("matches with Chinese punctuation removed", () => {
    expect(matchExactly("孔明！", zhugeLiang)).toBe(true);
  });
  it("does not match a typo (错字不容忍)", () => {
    expect(matchExactly("诸葛梁", zhugeLiang)).toBe(false);
  });
  it("does not match a different figure", () => {
    expect(matchExactly("曹操", zhugeLiang)).toBe(false);
  });
  it("does not match a partial name like 诸葛丞相 (must go through LLM)", () => {
    expect(matchExactly("诸葛丞相", zhugeLiang)).toBe(false);
  });
});
