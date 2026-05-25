<script lang="ts">
  // T16+T18: daily 模式页 + localStorage 防复玩 + 耗尽降级 UI
  import { onMount } from "svelte";
  import figures from "$lib/data/figures.json";
  import type { Figure } from "$lib/types";
  import { createGameState } from "$lib/game-state.svelte";
  import { matchExactly } from "$lib/match-exact";
  import {
    checkAnswerViaLLM,
    classifyResult,
    shouldConsumeClue,
    type CheckAnswerOutcome,
  } from "$lib/check-answer-client";
  import AnswerInput from "$lib/components/AnswerInput.svelte";
  import FailReveal from "$lib/components/FailReveal.svelte";
  import ShareButton from "$lib/components/ShareButton.svelte";

  interface DailyInfo {
    figure_id: string;
    date: string;
    day_index: number;
    mode: "fresh" | "replay";
  }

  let loadState = $state<"loading" | "ready" | "already" | "error">("loading");
  let dailyInfo = $state<DailyInfo | null>(null);
  let figure = $state<Figure | null>(null);
  let game = $state<ReturnType<typeof createGameState> | null>(null);
  // 002 T16: game_id (client 生成, 用于 game/finish 幂等)
  let gameId = $state(crypto.randomUUID());
  let userInput = $state("");
  let checking = $state(false);
  // 002 T15: loading 双阶段
  let checkingPhase = $state<"idle" | "fast" | "slow">("idle");
  let timer200: ReturnType<typeof setTimeout> | null = null;
  let timer5000: ReturnType<typeof setTimeout> | null = null;
  // 002 T14: 用 outcome 结构替代旧 {correct, via, reason}
  let lastResult = $state<{ input: string; outcome: CheckAnswerOutcome } | null>(null);
  let previousScore = $state<number | null>(null); // 已玩过显示历史分数
  let triggeredRescue = $state(false);
  let errorMsg = $state<string | null>(null);

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

  // 002 T16: 游戏结束自动 POST /api/game/finish + 写 localStorage (二者都覆盖
  // exhausted 路径; 旧代码只在 markWon/giveUp 后调用 onGameFinish, 漏 exhausted)
  $effect(() => {
    if (game?.finished) {
      // 写 server (幂等)
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

      // 写 localStorage (daily 防复玩)
      if (dailyInfo) {
        saveDailyResult(
          dailyInfo.date,
          game.score,
          game.won,
          game.revealedCount,
          triggeredRescue,
        );
      }
    }
  });

  function localStorageKey(date: string) {
    return `daily_played_${date}`;
  }

  function loadPreviousIfAny(date: string): number | null {
    try {
      const raw = localStorage.getItem(localStorageKey(date));
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return typeof parsed.score === "number" ? parsed.score : null;
    } catch {
      return null;
    }
  }

  function saveDailyResult(date: string, score: number, won: boolean, used: number, rescue: boolean) {
    try {
      localStorage.setItem(
        localStorageKey(date),
        JSON.stringify({ score, won, used, rescue, completed_at: new Date().toISOString() }),
      );
    } catch (e) {
      console.warn("localStorage 写入失败:", e);
    }
  }

  onMount(async () => {
    try {
      const r = await fetch("/api/daily");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      dailyInfo = (await r.json()) as DailyInfo;
    } catch (e) {
      errorMsg = `加载今日题失败: ${e instanceof Error ? e.message : String(e)}`;
      loadState = "error";
      return;
    }

    // 检查 localStorage 是否已玩过
    const prev = loadPreviousIfAny(dailyInfo.date);
    if (prev !== null) {
      previousScore = prev;
      loadState = "already";
      return;
    }

    // 找对应的 figure
    const f = (figures as Figure[]).find((x) => x.id === dailyInfo!.figure_id);
    if (!f) {
      errorMsg = `题库无 figure_id=${dailyInfo.figure_id}`;
      loadState = "error";
      return;
    }
    figure = f;
    game = createGameState(f);
    loadState = "ready";
  });

  async function handleSubmit(text: string) {
    if (!game || !figure) return;

    if (matchExactly(text, figure)) {
      lastResult = {
        input: text,
        outcome: { kind: "correct", reason: "异称表命中" },
      };
      game.markWon();
      // localStorage + server 写由 $effect(game.finished) 统一触发
      return;
    }

    checking = true;
    startLoadingTimers();
    const r = await checkAnswerViaLLM(text, figure);
    checking = false;
    clearLoadingTimers();

    const outcome = classifyResult(r);
    lastResult = { input: text, outcome };

    // SPEC G7: 仅 outcome.kind === "wrong" 才消耗线索
    if (outcome.kind === "correct") {
      game.markWon();
    } else if (shouldConsumeClue(outcome)) {
      game.consumeOnWrongAnswer();
      userInput = "";
    }
  }

  function triggerRescue() {
    if (game) {
      triggeredRescue = true;
      game.startRescue();
    }
  }

  function giveUp() {
    if (game) {
      game.giveUp();
      // localStorage + server 写由 $effect(game.finished) 统一触发
    }
  }
</script>

<svelte:head>
  <title>今日挑战 — 猜历史人物</title>
</svelte:head>

<main>
  <header>
    <h1>今日挑战</h1>
    {#if dailyInfo}
      <p class="subtitle">
        #{dailyInfo.day_index + 1} · {dailyInfo.date}
        {#if dailyInfo.mode === "replay"}
          · <span class="badge-replay">📚 经典回顾</span>
        {/if}
      </p>
    {/if}
  </header>

  {#if loadState === "loading"}
    <p class="loading">⏳ 加载今日题...</p>
  {:else if loadState === "error"}
    <p class="error">⚠️ {errorMsg}</p>
    <p><a href="/play">→ 改玩日常模式</a></p>
  {:else if loadState === "already" && dailyInfo}
    <section class="already-played">
      <h2>🎯 今日已完成</h2>
      <p>得分 <strong>{previousScore}</strong></p>
      <p class="hint">每日 0:00（北京时间）换新题。当天只能玩 1 次。</p>
      <p><a href="/play">→ 改玩日常模式</a></p>
    </section>
  {:else if loadState === "ready" && game && figure && dailyInfo}
    {#if game.finished}
      <FailReveal
        figure={game.figure}
        won={game.won}
        score={game.score}
        revealedCount={game.revealedCount}
        onretry={() => {}}
      />
      <ShareButton
        dayIndex={dailyInfo.day_index}
        revealedCount={game.revealedCount}
        won={game.won}
        rescue={triggeredRescue}
      />
      <p class="hint">每日 0:00（北京时间）换新题。<a href="/play">→ 改玩日常模式</a></p>
    {:else}
      <section class="meta">
        <span>线索 <strong>{game.revealedCount}/{game.totalClues}</strong></span>
        <span class="status">
          {game.inRescueRange ? "🆘 求救范围（最高 10 分）" : "标准范围"}
        </span>
      </section>

      <section class="clues">
        {#each game.visibleClues as clue, i (i)}
          <article class="clue clue-d{clue.difficulty}">
            <span class="badge">线索 {i + 1}</span>
            <p>{clue.text}</p>
          </article>
        {/each}
      </section>

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
          <button class="btn-secondary" onclick={() => game?.nextClue()}>
            再来一条线索（用 {game.revealedCount + 1} 条得 {(6 - (game.revealedCount + 1)) * 20} 分）
          </button>
        {:else if game.canRescue}
          <button class="btn-rescue" onclick={triggerRescue}>🆘 求救（再要 2 条，最高 10 分）</button>
        {:else if game.canNextRescueClue}
          <button class="btn-rescue" onclick={() => game?.nextRescueClue()}>再要一条求救线索</button>
        {:else}
          <p class="exhausted">📚 7 条线索全部展示完</p>
        {/if}
        <button class="btn-link" onclick={giveUp}>放弃看答案</button>
      </section>
    {/if}
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
  .badge-replay {
    background: var(--color-warning-bg);
    color: var(--color-warning);
    padding: 0.1rem 0.5rem;
    border-radius: 3px;
    font-size: 0.85em;
  }
  .loading,
  .error {
    text-align: center;
    padding: 2rem;
    color: var(--color-text-soft);
  }
  .error {
    color: var(--color-error);
  }
  .already-played {
    background: var(--color-success-bg);
    border: 1px solid var(--color-success-border);
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
  }
  .already-played h2 {
    margin: 0 0 0.8rem;
    font-size: 1.4rem;
  }
  .already-played strong {
    font-size: 2rem;
    color: var(--color-text);
  }
  .hint {
    color: var(--color-text-soft);
    font-size: 0.9rem;
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
  a {
    color: var(--color-primary);
  }
</style>
