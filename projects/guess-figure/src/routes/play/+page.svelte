<script lang="ts">
  import figures from "$lib/data/figures.json";
  import type { Figure } from "$lib/types";
  import { createGameState, pickRandomFigure } from "$lib/game-state.svelte";
  import { matchExactly } from "$lib/match-exact";
  import AnswerInput from "$lib/components/AnswerInput.svelte";

  // 随机抽一个人物作为当前局
  let game = $state(createGameState(pickRandomFigure(figures as Figure[])));
  let userInput = $state("");
  let lastResult = $state<{ input: string; correct: boolean; via: "exact" | "llm-pending"; reason?: string } | null>(null);

  function startNewGame() {
    game = createGameState(pickRandomFigure(figures as Figure[]));
    userInput = "";
    lastResult = null;
  }

  function handleSubmit(text: string) {
    // T8: 第一道 — 异称表精确匹配（前端，无 LLM 成本）
    if (matchExactly(text, game.figure)) {
      lastResult = { input: text, correct: true, via: "exact", reason: "异称表命中" };
      // T10 加计分 / T9 加 LLM fallback / T11 进 win 状态
      return;
    }

    // T9 会接 LLM fallback。当前先标记"待 LLM"。
    lastResult = { input: text, correct: false, via: "llm-pending", reason: "异称表未命中（T9 接 LLM fallback）" };
    userInput = "";
  }
</script>

<svelte:head>
  <title>日常游戏 — 猜历史人物</title>
</svelte:head>

<main>
  <header>
    <h1>日常游戏</h1>
    <p class="subtitle">5 条标准线索 + 2 条求救线索</p>
  </header>

  <section class="meta">
    <span>线索 <strong>{game.revealedCount}/{game.totalClues}</strong></span>
    <span class="status status-{game.status}">
      {#if game.status === "playing"}
        标准范围（猜中越早分越高）
      {:else if game.status === "rescue"}
        🆘 求救范围（最高 10 分）
      {/if}
    </span>
  </section>

  <section class="clues">
    {#each game.visibleClues as clue, i (i)}
      <article class="clue clue-d{clue.difficulty}">
        <span class="badge">线索 {i + 1}</span>
        <p class="text">{clue.text}</p>
      </article>
    {/each}
  </section>

  <section class="input">
    <AnswerInput bind:value={userInput} onsubmit={handleSubmit} />
    {#if lastResult}
      <p class="result result-{lastResult.correct ? 'ok' : 'no'}">
        {lastResult.correct ? "✅ 算对" : "❌ 不算"}「{lastResult.input}」 —
        <small>{lastResult.reason}（{lastResult.via}）</small>
      </p>
    {/if}
  </section>

  <section class="actions">
    {#if game.canNextClue}
      <button class="btn-secondary" onclick={() => game.nextClue()}>
        再来一条线索
      </button>
    {:else if game.canRescue}
      <button class="btn-rescue" onclick={() => game.startRescue()}>
        🆘 求救（再要 2 条线索）
      </button>
    {:else if game.canNextRescueClue}
      <button class="btn-rescue" onclick={() => game.nextRescueClue()}>
        再要一条求救线索
      </button>
    {:else}
      <p class="exhausted">📚 7 条线索全部展示完。（T11/T12 后续：放弃看答案 UI）</p>
    {/if}

    <button class="btn-link" onclick={startNewGame}>
      换一个人物
    </button>
  </section>

  <details class="debug">
    <summary>🔧 调试信息（开发期）</summary>
    <pre>当前人物: {game.figure.name}
异称: {game.figure.aliases.join("、")}
revealedCount: {game.revealedCount}
status: {game.status}
canNextClue: {game.canNextClue}
canRescue: {game.canRescue}
canNextRescueClue: {game.canNextRescueClue}</pre>
  </details>
</main>

<style>
  main {
    max-width: 680px;
    margin: 2rem auto;
    padding: 1.5rem;
    font-family: system-ui, -apple-system, "Microsoft YaHei", sans-serif;
    line-height: 1.7;
    color: #1f2937;
  }
  header h1 {
    font-size: 1.6rem;
    margin: 0;
  }
  .subtitle {
    color: #6b7280;
    margin: 0.3rem 0 1.5rem;
    font-size: 0.95rem;
  }
  .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0.9rem;
    background: #f9fafb;
    border-radius: 6px;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
  }
  .meta strong {
    color: #2563eb;
  }
  .status-playing {
    color: #059669;
  }
  .status-rescue {
    color: #dc2626;
    font-weight: 600;
  }
  .clues {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    margin-bottom: 1.5rem;
  }
  .clue {
    padding: 0.85rem 1rem;
    background: #fff;
    border-left: 4px solid #e5e7eb;
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  }
  .clue-d6,
  .clue-d7 {
    border-left-color: #fbbf24;
    background: #fffbeb;
  }
  .badge {
    display: inline-block;
    background: #eef;
    color: #4338ca;
    padding: 0.1rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    margin-bottom: 0.3rem;
  }
  .text {
    margin: 0.2rem 0 0;
  }
  .input {
    margin-bottom: 1.25rem;
  }
  .result {
    margin: 0.6rem 0 0;
    padding: 0.6rem 0.85rem;
    border-radius: 4px;
    font-size: 0.92rem;
  }
  .result-ok {
    background: #ecfdf5;
    border-left: 3px solid #10b981;
    color: #065f46;
  }
  .result-no {
    background: #fef2f2;
    border-left: 3px solid #ef4444;
    color: #991b1b;
  }
  .result small {
    color: inherit;
    opacity: 0.75;
  }
  .actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }
  button {
    cursor: pointer;
    font-size: 0.95rem;
  }
  .btn-secondary {
    padding: 0.55rem 1.1rem;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 4px;
  }
  .btn-rescue {
    padding: 0.55rem 1.1rem;
    background: #f59e0b;
    color: white;
    border: none;
    border-radius: 4px;
  }
  .btn-link {
    padding: 0.5rem 0.8rem;
    background: none;
    color: #6b7280;
    border: 1px solid #d1d5db;
    border-radius: 4px;
  }
  .exhausted {
    color: #6b7280;
    margin: 0;
    font-size: 0.9rem;
  }
  .debug {
    margin-top: 2rem;
    padding: 0.8rem;
    background: #f3f4f6;
    border-radius: 4px;
    font-size: 0.85rem;
    color: #6b7280;
  }
  .debug summary {
    cursor: pointer;
    user-select: none;
  }
  .debug pre {
    margin: 0.5rem 0 0;
    white-space: pre-wrap;
  }
</style>
