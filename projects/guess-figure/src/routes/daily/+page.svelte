<script lang="ts">
  // T16+T18: daily 模式页 + localStorage 防复玩 + 耗尽降级 UI
  import { onMount } from "svelte";
  import figures from "$lib/data/figures.json";
  import type { Figure } from "$lib/types";
  import { createGameState } from "$lib/game-state.svelte";
  import { matchExactly } from "$lib/match-exact";
  import { checkAnswerViaLLM } from "$lib/check-answer-client";
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
  let userInput = $state("");
  let checking = $state(false);
  let lastResult = $state<{ input: string; correct: boolean; via: string; reason?: string } | null>(null);
  let previousScore = $state<number | null>(null); // 已玩过显示历史分数
  let triggeredRescue = $state(false);
  let errorMsg = $state<string | null>(null);

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
      lastResult = { input: text, correct: true, via: "exact", reason: "异称表命中" };
      game.markWon();
      onGameFinish();
      return;
    }

    checking = true;
    const r = await checkAnswerViaLLM(text, figure);
    checking = false;

    if ("error" in r) {
      lastResult = { input: text, correct: false, via: "error", reason: r.error };
      return;
    }

    lastResult = { input: text, correct: r.correct, via: "llm", reason: r.reason };
    if (r.correct) {
      game.markWon();
      onGameFinish();
    } else {
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
      onGameFinish();
    }
  }

  function onGameFinish() {
    if (!game || !dailyInfo) return;
    saveDailyResult(
      dailyInfo.date,
      game.score,
      game.won,
      game.revealedCount,
      triggeredRescue,
    );
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
          <p class="result result-checking">⏳ LLM 判定中...</p>
        {:else if lastResult}
          <p class="result result-{lastResult.correct ? 'ok' : lastResult.via === 'error' ? 'err' : 'no'}">
            {lastResult.correct ? "✅ 算对" : lastResult.via === "error" ? "⚠️ 出错" : "❌ 不算"}「{lastResult.input}」
            <small>— {lastResult.reason}</small>
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
  .badge-replay {
    background: #fef3c7;
    color: #92400e;
    padding: 0.1rem 0.5rem;
    border-radius: 3px;
    font-size: 0.85em;
  }
  .loading,
  .error {
    text-align: center;
    padding: 2rem;
    color: #6b7280;
  }
  .error {
    color: #991b1b;
  }
  .already-played {
    background: #ecfdf5;
    border: 1px solid #10b981;
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
    color: #1f2937;
  }
  .hint {
    color: #6b7280;
    font-size: 0.9rem;
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
  .result-err {
    background: #fefce8;
    border-left: 3px solid #eab308;
    color: #854d0e;
  }
  .result-checking {
    background: #eff6ff;
    border-left: 3px solid #3b82f6;
    color: #1e40af;
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
  a {
    color: #2563eb;
  }
</style>
