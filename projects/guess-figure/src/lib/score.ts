// T10: 计分公式（SPEC 决策 7b）
//
// 标准范围（k=1-5）: 100 / 80 / 60 / 40 / 20
// 求救范围（k=6-7）: 10
// 放弃 / 7 条用完未猜中: 0
//
// SPEC AC9 要求：单元测试覆盖 (6-k)*20 / 求救 10 / 放弃 0。
// 单测推到 T15。本函数当前用浏览器多次玩验证 1 条 100 / 2 条 80 / ... / 6 条 10。

export function calculateScore(usedClues: number, won: boolean): number {
  if (!won) return 0;
  if (usedClues >= 1 && usedClues <= 5) return (6 - usedClues) * 20; // 100/80/60/40/20
  if (usedClues >= 6 && usedClues <= 7) return 10; // 求救范围
  return 0;
}
