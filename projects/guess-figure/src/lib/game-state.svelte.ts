// 游戏状态机（Svelte 5 runes）
// T6: 线索状态机（当前展示几条 / 标准 vs 求救范围 / nextClue）
// T10/T11/T12: 加计分 + won/revealed 状态 + giveUp

import type { Figure, GameStatus } from "./types";
import { calculateScore } from "./score";

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
  let won = $state(false);
  let gaveUp = $state(false);

  const visibleClues = $derived(figure.clues.slice(0, revealedCount));
  const totalClues = figure.clues.length; // 应该 = 7

  // 标准范围 1-5；求救范围 6-7
  const inRescueRange = $derived(revealedCount > 5);

  // 游戏结束：猜中 / 放弃 / 7 条全用完
  const exhausted = $derived(revealedCount >= totalClues && !won);
  const finished = $derived(won || gaveUp || exhausted);

  const status = $derived<GameStatus>(
    won ? "won" : finished ? "revealed" : inRescueRange ? "rescue" : "playing",
  );

  const score = $derived(calculateScore(revealedCount, won));

  // 还能不能点"再来一条"（标准范围内还有剩余）
  const canNextClue = $derived(!finished && revealedCount < 5);

  // 标准范围用完 → 可以触发求救（展示求救按钮 UI）
  const canRescue = $derived(!finished && revealedCount === 5);

  // 求救范围内还能不能点"再要一条"（求救从 6 到 7）
  const canNextRescueClue = $derived(!finished && revealedCount >= 6 && revealedCount < totalClues);

  // 是否能输入答案（未结束时）
  const canSubmit = $derived(!finished);

  function nextClue() {
    if (revealedCount < 5 && !finished) {
      revealedCount += 1;
    }
  }

  function startRescue() {
    if (revealedCount === 5 && !finished) {
      revealedCount = 6;
    }
  }

  function nextRescueClue() {
    if (revealedCount >= 6 && revealedCount < totalClues && !finished) {
      revealedCount += 1;
    }
  }

  function markWon() {
    if (!finished) {
      won = true;
    }
  }

  function giveUp() {
    if (!finished) {
      gaveUp = true;
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
    get won() {
      return won;
    },
    get gaveUp() {
      return gaveUp;
    },
    get finished() {
      return finished;
    },
    get score() {
      return score;
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
    get canSubmit() {
      return canSubmit;
    },
    nextClue,
    startRescue,
    nextRescueClue,
    markWon,
    giveUp,
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
