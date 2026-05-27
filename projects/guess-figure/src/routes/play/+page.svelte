<script lang="ts">
  import figures from "$lib/data/figures.json";
  import type { Figure } from "$lib/types";
  import { createGameState, pickRandomFigure } from "$lib/game-state.svelte";
  import { matchExactly } from "$lib/match-exact";
  import {
    checkAnswerViaLLM,
    classifyResult,
    shouldConsumeClue,
    type CheckAnswerOutcome,
  } from "$lib/check-answer-client";
  import AnswerInput from "$lib/components/AnswerInput.svelte";
  import FailReveal from "$lib/components/FailReveal.svelte";
  import TurtleHelpPanel from "$lib/components/TurtleHelpPanel.svelte";

  // 随机抽一个人物作为当前局
  let game = $state(createGameState(pickRandomFigure(figures as Figure[])));
  // 002 T16: 每局 game_id (client 生成, 幂等所需)
  let gameId = $state(crypto.randomUUID());
  let userInput = $state("");
  let checking = $state(false);
  // 002 T15: loading 双阶段 (200ms / 5s 后切换文案)
  let checkingPhase = $state<"idle" | "fast" | "slow">("idle");
  let timer200: ReturnType<typeof setTimeout> | null = null;
  let timer5000: ReturnType<typeof setTimeout> | null = null;
  // 002 T14: 用 outcome 结构替代旧 {correct, via, reason}
  let lastResult = $state<{ input: string; outcome: CheckAnswerOutcome } | null>(null);

  function startNewGame() {
    game = createGameState(pickRandomFigure(figures as Figure[]));
    gameId = crypto.randomUUID();
    userInput = "";
    lastResult = null;
  }

  function startLoadingTimers() {
    checkingPhase = "idle";
    timer200 = setTimeout(() => {
      checkingPhase = "fast";
    }, 200);
    timer5000 = setTimeout(() => {
      checkingPhase = "slow";
    }, 5000);
  }
  function clearLoadingTimers() {
    if (timer200) clearTimeout(timer200);
    if (timer5000) clearTimeout(timer5000);
    timer200 = null;
    timer5000 = null;
    checkingPhase = "idle";
  }

  // 002 T16: 游戏结束自动 POST /api/game/finish (幂等, 不阻塞 UI)
  $effect(() => {
    if (game.finished) {
      const snapshot = {
        game_id: gameId,
        figure_id: game.figure.id,
        won: game.won,
        revealed_count: game.revealedCount,
        score: game.score,
        given_up: game.gaveUp,
      };
      fetch("/api/game/finish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snapshot),
      }).catch((e) => console.warn("[game/finish] 失败 (不阻塞 UI):", e));
    }
  });

  async function handleSubmit(text: string) {
    // 第一道 — 异称表精确匹配（前端，无 LLM 成本, 不调 server）
    if (matchExactly(text, game.figure)) {
      lastResult = {
        input: text,
        outcome: { kind: "correct", reason: "异称表命中" },
      };
      game.markWon();
      return;
    }

    // 第二道 — server pipeline (normalize → server match-exact → cache → LLM)
    checking = true;
    startLoadingTimers();
    const r = await checkAnswerViaLLM(text, game.figure);
    checking = false;
    clearLoadingTimers();

    const outcome = classifyResult(r);
    lastResult = { input: text, outcome };

    // SPEC G7: 仅 outcome.kind === "wrong" 才消耗线索;
    // correct → markWon; degraded/network_error/client_error 都不消耗
    if (outcome.kind === "correct") {
      game.markWon();
    } else if (shouldConsumeClue(outcome)) {
      game.consumeOnWrongAnswer();
      userInput = "";
    }
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

  {#if game.finished}
    <FailReveal
      figure={game.figure}
      won={game.won}
      score={game.score}
      revealedCount={game.revealedCount}
      onretry={startNewGame}
    />
  {:else}
    {#if game.canUseTurtleHelp}
      <TurtleHelpPanel
        figureId={game.figure.id}
        {gameId}
        questionsRemaining={game.turtleQuestionsRemaining}
        canAskQuestion={game.canAskTurtleQuestion}
        onQuestionConsumed={() => game.markTurtleQuestionConsumed()}
      />
    {/if}

    <section class="input">
      <AnswerInput bind:value={userInput} disabled={checking} onsubmit={handleSubmit} />
      {#if checking}
        <p class="result result-checking">
          {#if checkingPhase === "slow"}
            ⏳ AI 正在思考较复杂的输入...
          {:else if checkingPhase === "fast"}
            ⏳ AI 裁判中...
          {:else}
            ⏳
          {/if}
        </p>
      {:else if lastResult}
        {@const outcome = lastResult.outcome}
        <p
          class="result result-{outcome.kind === 'correct'
            ? 'ok'
            : outcome.kind === 'wrong'
              ? 'no'
              : 'err'}"
        >
          {#if outcome.kind === "correct"}
            ✅ 算对「{lastResult.input}」
          {:else if outcome.kind === "wrong"}
            ❌ 不算「{lastResult.input}」
          {:else if outcome.kind === "degraded"}
            ⚠️ {outcome.reason}
          {:else if outcome.kind === "network_error"}
            ⚠️ {outcome.reason}（不消耗线索，请稍后重试）
          {:else}
            ⚠️ 提交失败：{outcome.reason}
          {/if}
        </p>
      {/if}
    </section>

    <section class="actions">
      {#if game.canNextClue}
        <button class="btn-secondary" onclick={() => game.nextClue()}>
          再来一条线索（用 {game.revealedCount + 1} 条得 {(6 - (game.revealedCount + 1)) * 20} 分）
        </button>
      {:else if game.canRescue}
        <button class="btn-rescue" onclick={() => game.startRescue()}>
          🆘 求救（再要 2 条线索，最高 10 分）
        </button>
      {:else if game.canNextRescueClue}
        <button class="btn-rescue" onclick={() => game.nextRescueClue()}>
          再要一条求救线索
        </button>
      {:else}
        <p class="exhausted">📚 7 条线索全部展示完</p>
      {/if}

      <button class="btn-link" onclick={() => game.giveUp()}>放弃看答案</button>
      <button class="btn-link" onclick={startNewGame}>换一个人物</button>
    </section>
  {/if}

</main>

<style>
  main {
    max-width: 680px;
    margin: 2rem auto;
    padding: 1.5rem;
    font-family: system-ui, -apple-system, "Microsoft YaHei", sans-serif;
    line-height: 1.7;
    color: var(--color-text);
  }
  header h1 {
    font-size: 1.6rem;
    margin: 0;
  }
  .subtitle {
    color: var(--color-text-soft);
    margin: 0.3rem 0 1.5rem;
    font-size: 0.95rem;
  }
  .meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0.9rem;
    background: var(--color-bg-card);
    border-radius: 6px;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
  }
  .meta strong {
    color: var(--color-primary);
  }
  .status-playing {
    color: var(--color-success);
  }
  .status-rescue {
    color: var(--color-primary);
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
    background: var(--color-bg-card);
    border-left: 4px solid var(--color-border-soft);
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  }
  .clue-d6,
  .clue-d7 {
    border-left-color: var(--color-accent);
    background: var(--color-warning-bg);
  }
  .badge {
    display: inline-block;
    background: var(--color-bg-card);
    color: var(--color-primary);
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
    background: var(--color-success-bg);
    border-left: 3px solid var(--color-success-border);
    color: var(--color-success);
  }
  .result-no {
    background: var(--color-error-bg);
    border-left: 3px solid var(--color-error-border);
    color: var(--color-error);
  }
  .result-err {
    background: var(--color-warning-bg);
    border-left: 3px solid var(--color-warning-border);
    color: var(--color-warning);
  }
  .result-checking {
    background: var(--color-info-bg);
    border-left: 3px solid var(--color-primary);
    color: var(--color-primary);
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
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 4px;
  }
  .btn-rescue {
    padding: 0.55rem 1.1rem;
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: 4px;
  }
  .btn-link {
    padding: 0.5rem 0.8rem;
    background: none;
    color: var(--color-text-soft);
    border: 1px solid var(--color-border);
    border-radius: 4px;
  }
  .exhausted {
    color: var(--color-text-soft);
    margin: 0;
    font-size: 0.9rem;
  }
</style>
