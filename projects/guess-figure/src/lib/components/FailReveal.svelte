<script lang="ts">
  // T12: 失败 / 放弃显示答案 + 维基链接 + 再玩一局
  //
  // SPEC OQ5: 一句话简介 + 维基链接（V1 极简版）
  // V1 暂用 figure.name + wiki_url（不含丰富简介，V2 可加）

  import type { Figure } from "$lib/types";

  interface Props {
    figure: Figure;
    won: boolean;
    score: number;
    revealedCount: number;
    onretry: () => void;
  }

  let { figure, won, score, revealedCount, onretry }: Props = $props();
</script>

<section class="reveal {won ? 'won' : 'lost'}">
  {#if won}
    <h2>✅ 猜中了！</h2>
    <p class="score">
      得分 <strong>{score}</strong>
      <small>（用了 {revealedCount} 条线索）</small>
    </p>
  {:else}
    <h2>❌ 答案揭晓</h2>
    <p class="score">得分 <strong>0</strong></p>
  {/if}

  <div class="answer">
    <p class="name">{figure.name}</p>
    {#if figure.aliases?.length}
      <p class="aliases">别号 / 字 / 号: {figure.aliases.join("、")}</p>
    {/if}
    <p class="link">
      <a href={figure.wiki_url} target="_blank" rel="noopener">📖 维基百科查看详情 →</a>
    </p>
  </div>

  <button class="btn-retry" onclick={onretry}>换一个人物再玩</button>
</section>

<style>
  .reveal {
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1.5rem 0;
  }
  .reveal.won {
    background: linear-gradient(to bottom, var(--color-success-bg), var(--color-success-bg));
    border: 1px solid var(--color-success-border);
  }
  .reveal.lost {
    background: linear-gradient(to bottom, var(--color-error-bg), var(--color-error-bg));
    border: 1px solid var(--color-error-border);
  }
  h2 {
    margin: 0 0 0.8rem;
    font-size: 1.4rem;
  }
  .score {
    margin: 0 0 1rem;
    font-size: 1.05rem;
  }
  .score strong {
    font-size: 1.5rem;
    color: var(--color-text);
  }
  .score small {
    color: var(--color-text-soft);
    font-weight: normal;
  }
  .answer {
    background: var(--color-bg-card);
    padding: 1rem 1.2rem;
    border-radius: 6px;
    margin-bottom: 1.2rem;
  }
  .name {
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0 0 0.5rem;
    color: var(--color-text);
  }
  .aliases {
    color: var(--color-text-soft);
    font-size: 0.9rem;
    margin: 0 0 0.6rem;
  }
  .link {
    margin: 0;
  }
  .link a {
    color: var(--color-primary);
    text-decoration: none;
    font-size: 0.95rem;
  }
  .link a:hover {
    text-decoration: underline;
  }
  .btn-retry {
    padding: 0.65rem 1.4rem;
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.95rem;
  }
</style>
