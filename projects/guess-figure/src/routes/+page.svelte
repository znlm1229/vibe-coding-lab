<script lang="ts">
  // T19: 首页双入口 + fix(T16): 加 /api/me 个人战绩 stats 区段
  import { onMount } from "svelte";
  import figures from "$lib/data/figures.json";
  import type { Figure } from "$lib/types";

  let dailyPlayedToday = $state(false);
  let dailyScore = $state<number | null>(null);
  let dailyDate = $state<string | null>(null);

  interface RecentGame {
    id: string;
    figure_id: string;
    won: number;
    revealed_count: number;
    score: number;
    given_up: number;
    played_at: string;
  }
  interface MeStats {
    total_games: number;
    total_wins: number;
    total_score_30d: number;
    recent_games: RecentGame[];
  }

  let myStats = $state<MeStats | null>(null);
  let statsError = $state<string | null>(null);

  // figures.json 按 id 查 name 用 (recent_games 仅返 figure_id)
  const figureMap = new Map((figures as Figure[]).map((f) => [f.id, f.name]));

  function formatPlayedAt(iso: string): string {
    // D1 返 "YYYY-MM-DD HH:MM:SS" UTC; 转用户本地, 显示 "M月D日" 或 "今天"
    const d = new Date(iso.replace(" ", "T") + "Z");
    if (Number.isNaN(d.getTime())) return iso;
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    if (sameDay) return "今天";
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }

  onMount(async () => {
    // 检查 daily 今日是否已玩
    try {
      const r = await fetch("/api/daily");
      if (r.ok) {
        const info = (await r.json()) as { date: string };
        dailyDate = info.date;
        const raw = localStorage.getItem(`daily_played_${info.date}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          dailyPlayedToday = true;
          dailyScore = typeof parsed.score === "number" ? parsed.score : null;
        }
      }
    } catch {
      // 静默失败 — 首页不依赖 daily 状态展示
    }

    // 拉个人战绩 (fix(T16) 002 完整 UI)
    try {
      const r = await fetch("/api/me");
      if (r.ok) {
        myStats = (await r.json()) as MeStats;
      } else {
        statsError = `加载失败 (HTTP ${r.status})`;
      }
    } catch (e) {
      statsError = `加载失败: ${e instanceof Error ? e.message : "网络错误"}`;
    }
  });
</script>

<svelte:head>
  <title>猜历史人物</title>
</svelte:head>

<main>
  <header>
    <h1>猜历史人物</h1>
    <p class="tagline">5 条线索，你能猜出他是谁？</p>
  </header>

  <section class="entries">
    <a href="/play" class="entry entry-play">
      <h2>🎮 日常游戏</h2>
      <p>从 50 个中国历史人物中随机抽题，无限玩。</p>
    </a>

    <a href="/daily" class="entry entry-daily">
      <h2>📅 今日挑战</h2>
      {#if dailyPlayedToday && dailyScore !== null}
        <p>今日已完成：<strong>{dailyScore} 分</strong>（明日 0:00 换新题）</p>
      {:else}
        <p>全球同题，每日 1 次，可分享成绩。</p>
      {/if}
    </a>
  </section>

  <!-- fix(T16) 002 完整 UI: 个人战绩区段 -->
  <section class="my-stats">
    <h2>📊 我的战绩</h2>
    {#if statsError}
      <p class="stats-error">{statsError}</p>
    {:else if myStats === null}
      <p class="stats-loading">加载中…</p>
    {:else if myStats.total_games === 0}
      <p class="stats-empty">开始第一局来记录你的战绩吧 ↑</p>
    {:else}
      <p class="stats-summary">
        共玩 <strong>{myStats.total_games}</strong> 局
        · 胜 <strong>{myStats.total_wins}</strong> 局
        {#if myStats.total_score_30d > 0}
          · 近 30 天 <strong>{myStats.total_score_30d}</strong> 分
        {/if}
      </p>
      {#if myStats.recent_games.length > 0}
        <ul class="recent-list">
          {#each myStats.recent_games as g (g.id)}
            <li>
              <span class="game-icon">
                {#if g.won}✓{:else if g.given_up}⊘{:else}✗{/if}
              </span>
              <span class="game-name">{figureMap.get(g.figure_id) ?? g.figure_id}</span>
              <span class="game-score">{g.score} 分</span>
              <span class="game-date">{formatPlayedAt(g.played_at)}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </section>
</main>

<style>
  main {
    max-width: 680px;
    margin: 3rem auto;
    padding: 2rem;
    font-family: system-ui, -apple-system, "Microsoft YaHei", sans-serif;
    line-height: 1.7;
    color: var(--color-text);
  }
  header h1 {
    font-size: 2.2rem;
    margin: 0;
    text-align: center;
  }
  .tagline {
    text-align: center;
    color: var(--color-text-soft);
    margin: 0.5rem 0 2.5rem;
    font-size: 1.05rem;
  }
  .entries {
    display: grid;
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .entry {
    display: block;
    padding: 1.5rem;
    background: var(--color-bg-card);
    border: 2px solid var(--color-border-soft);
    border-radius: 10px;
    text-decoration: none;
    color: inherit;
    transition: all 0.15s;
  }
  .entry:hover {
    border-color: var(--color-primary);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
    transform: translateY(-1px);
  }
  .entry h2 {
    margin: 0 0 0.5rem;
    font-size: 1.3rem;
  }
  .entry p {
    margin: 0;
    color: var(--color-text-soft);
    font-size: 0.95rem;
  }
  .entry-play:hover {
    border-color: var(--color-primary);
  }
  .entry-daily:hover {
    border-color: var(--color-success-border);
  }
  .entry-daily strong {
    color: var(--color-success);
  }

  /* fix(T16) 002 完整 UI: 个人战绩区段 */
  .my-stats {
    margin-top: 2.5rem;
    padding: 1.5rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-soft);
    border-radius: 10px;
  }
  .my-stats h2 {
    margin: 0 0 1rem;
    font-size: 1.15rem;
    color: var(--color-text);
  }
  .stats-loading,
  .stats-empty,
  .stats-error {
    color: var(--color-text-soft);
    font-size: 0.95rem;
    margin: 0;
  }
  .stats-error {
    color: var(--color-danger, #c0392b);
  }
  .stats-summary {
    margin: 0 0 0.75rem;
    font-size: 0.95rem;
    color: var(--color-text);
  }
  .stats-summary strong {
    color: var(--color-primary);
    font-weight: 600;
  }
  .recent-list {
    margin: 0.5rem 0 0;
    padding: 0;
    list-style: none;
  }
  .recent-list li {
    display: grid;
    grid-template-columns: 1.5rem 1fr auto auto;
    gap: 0.75rem;
    align-items: center;
    padding: 0.4rem 0;
    border-top: 1px solid var(--color-border-soft);
    font-size: 0.9rem;
  }
  .recent-list li:first-child {
    border-top: none;
  }
  .game-icon {
    text-align: center;
    color: var(--color-text-soft);
  }
  .game-name {
    color: var(--color-text);
  }
  .game-score {
    color: var(--color-text-soft);
    font-variant-numeric: tabular-nums;
  }
  .game-date {
    color: var(--color-text-soft);
    font-size: 0.85rem;
  }
</style>
