// 游戏状态机（Svelte 5 runes）
// T6: 实现线索状态机（当前展示几条 / 标准 vs 求救范围 / nextClue）
// T7-T11 后续 task 扩展：输入提交 / 异称匹配 / 求救 / 失败显示

import type { Figure, GameStatus } from "./types";

/**
 * 创建一局游戏的状态机。
 *
 * 用法（在 Svelte 组件 <script> 中）：
 *   const game = createGameState(figure);
 *   // game.visibleClues / game.canNextClue / game.status
 *   game.nextClue();
 */
export function createGameState(figure: Figure) {
  // 当前已展示的线索数（1-7）。初始 1 条已展示。
  let revealedCount = $state(1);

  const visibleClues = $derived(figure.clues.slice(0, revealedCount));
  const totalClues = figure.clues.length; // 应该 = 7

  // 标准范围 1-5；求救范围 6-7
  const inRescueRange = $derived(revealedCount > 5);
  const status = $derived<GameStatus>(inRescueRange ? "rescue" : "playing");

  // 还能不能点"再来一条"（标准范围内还有剩余）
  const canNextClue = $derived(revealedCount < 5);

  // 标准范围用完 → 可以触发求救（展示求救按钮 UI）
  const canRescue = $derived(revealedCount === 5);

  // 求救范围内还能不能点"再要一条"（求救从 6 到 7）
  const canNextRescueClue = $derived(revealedCount >= 5 && revealedCount < totalClues);

  function nextClue() {
    if (revealedCount < 5) {
      revealedCount += 1;
    }
  }

  function startRescue() {
    // 5 条用完时把第 6 条展示出来（即"求救一次"）
    if (revealedCount === 5) {
      revealedCount = 6;
    }
  }

  function nextRescueClue() {
    if (revealedCount >= 5 && revealedCount < totalClues) {
      revealedCount += 1;
    }
  }

  return {
    figure,
    get revealedCount() {
      return revealedCount;
    },
    get visibleClues() {
      return visibleClues;
    },
    get totalClues() {
      return totalClues;
    },
    get status() {
      return status;
    },
    get inRescueRange() {
      return inRescueRange;
    },
    get canNextClue() {
      return canNextClue;
    },
    get canRescue() {
      return canRescue;
    },
    get canNextRescueClue() {
      return canNextRescueClue;
    },
    nextClue,
    startRescue,
    nextRescueClue,
  };
}

/**
 * 从题库随机抽一个人物。
 */
export function pickRandomFigure(figures: Figure[]): Figure {
  if (!figures.length) {
    throw new Error("题库为空");
  }
  const idx = Math.floor(Math.random() * figures.length);
  return figures[idx];
}
