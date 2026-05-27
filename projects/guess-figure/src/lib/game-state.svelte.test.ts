import { describe, expect, it } from "vitest";
import { createGameState } from "./game-state.svelte";
import type { Figure } from "./types";
import turtleHelpPanelSource from "$lib/components/TurtleHelpPanel.svelte?raw";

const figure: Figure = {
  id: "test-figure",
  name: "测试人物",
  aliases: ["测试"],
  clues: Array.from({ length: 7 }, (_, index) => ({
    text: `线索 ${index + 1}`,
    difficulty: index + 1,
  })),
  source: "test",
  wikidata_id: "Q0",
  wiki_url: "https://example.com",
};

function revealToSixthClue(game: ReturnType<typeof createGameState>) {
  game.nextClue();
  game.nextClue();
  game.nextClue();
  game.nextClue();
  game.startRescue();
}

describe("createGameState 嵌入式海龟汤", () => {
  it("TurtleHelpPanel 调用 question API 时发送 game_id", () => {
    const questionPayload = turtleHelpPanelSource.slice(
      turtleHelpPanelSource.indexOf('fetch("/api/turtle/question"'),
      turtleHelpPanelSource.indexOf(
        "});",
        turtleHelpPanelSource.indexOf('fetch("/api/turtle/question"'),
      ),
    );

    expect(questionPayload).toContain("game_id: gameId");
  });

  it("第 1-5 条线索不显示入口，第 6 条线索后显示入口", () => {
    const game = createGameState(figure);

    expect(game.canUseTurtleHelp).toBe(false);
    game.nextClue();
    game.nextClue();
    game.nextClue();
    game.nextClue();
    expect(game.revealedCount).toBe(5);
    expect(game.canUseTurtleHelp).toBe(false);

    game.startRescue();

    expect(game.revealedCount).toBe(6);
    expect(game.canUseTurtleHelp).toBe(true);
  });

  it("最多记录 5 个消耗次数的有效问题", () => {
    const game = createGameState(figure);
    revealToSixthClue(game);

    for (let i = 0; i < 5; i += 1) {
      expect(game.canAskTurtleQuestion).toBe(true);
      game.markTurtleQuestionConsumed();
    }

    expect(game.turtleQuestionsUsed).toBe(5);
    expect(game.turtleQuestionsRemaining).toBe(0);
    expect(game.canAskTurtleQuestion).toBe(false);

    game.markTurtleQuestionConsumed();

    expect(game.turtleQuestionsUsed).toBe(5);
  });

  it("实际使用嵌入式海龟汤后，获胜分数归零", () => {
    const game = createGameState(figure);
    revealToSixthClue(game);
    game.markTurtleHelpUsed();
    game.markWon();

    expect(game.turtleHelpUsed).toBe(true);
    expect(game.score).toBe(0);
  });
});
