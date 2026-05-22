<script lang="ts">
  // T19: 首页双入口
  import { onMount } from "svelte";

  let dailyPlayedToday = $state(false);
  let dailyScore = $state<number | null>(null);
  let dailyDate = $state<string | null>(null);

  onMount(async () => {
    // 检查 daily 今日是否已玩
    try {
      const r = await fetch("/api/daily");
      if (!r.ok) return;
      const info = (await r.json()) as { date: string };
      dailyDate = info.date;
      const raw = localStorage.getItem(`daily_played_${info.date}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        dailyPlayedToday = true;
        dailyScore = typeof parsed.score === "number" ? parsed.score : null;
      }
    } catch {
      // 静默失败 — 首页不依赖 daily 状态展示
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
</style>
