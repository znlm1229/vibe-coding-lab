// T8: 异称表精确匹配 + 输入规范化（前端，无需调 LLM）
//
// SPEC 决策 5: 两段式容错
// - 第一道: 异称表精确匹配（命中 95% 玩家，无 LLM 成本）
// - 第二道: LLM fallback（异称表外的常见组合，如"诸葛丞相"）
//
// 本文件实现第一道。LLM fallback 在 T9 + T13 实现。

import type { Figure } from "./types";

/**
 * 输入规范化：去空白 / 去标点 / 全→半角 / 小写。
 *
 * 故意不做的事:
 * - 繁→简转换: V1 不做（需要 OpenCC 库 ~700KB），靠 LLM fallback 兜底
 * - 错别字纠正: V1 决策 5 明示"错字不容忍"（避免"诸葛梁"被算对）
 */
export function normalize(input: string): string {
  return input
    .trim()
    .replace(/\s+/g, "") // 所有空白字符合并删除
    .replace(/[「」『』《》〈〉，。、；：？！…—·　 ()（）\[\]【】]/g, "") // 中文标点 + 全角空格 + 括号
    .toLowerCase();
}

/**
 * 异称表精确匹配。
 * 输入规范化后 === 目标本名或任一异称的规范化版本 → true。
 *
 * 例（target = 诸葛亮，aliases = [孔明, 卧龙, 武乡侯, 忠武侯]）:
 *   matchExactly("诸葛亮", target) → true
 *   matchExactly("孔明", target) → true
 *   matchExactly("  孔明  ", target) → true (去空白)
 *   matchExactly("孔 明", target) → true (去空白)
 *   matchExactly("孔明！", target) → true (去标点)
 *   matchExactly("诸葛梁", target) → false (错字不容忍)
 *   matchExactly("曹操", target) → false (不同人物)
 *   matchExactly("诸葛丞相", target) → false (走 LLM fallback)
 */
export function matchExactly(input: string, figure: Figure): boolean {
  const normalizedInput = normalize(input);
  if (!normalizedInput) return false;

  const candidates = [figure.name, ...figure.aliases];
  for (const cand of candidates) {
    if (cand && normalize(cand) === normalizedInput) {
      return true;
    }
  }
  return false;
}
