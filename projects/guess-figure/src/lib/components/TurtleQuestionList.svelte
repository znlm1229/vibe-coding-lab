<script lang="ts">
  import type { TurtleSoupQuestionEntry } from "$lib/turtle-soup-state";

  interface Props {
    questions: TurtleSoupQuestionEntry[];
  }

  let { questions }: Props = $props();
</script>

<section class="question-list" aria-live="polite">
  {#if questions.length === 0}
    <p class="empty">还没有提问。</p>
  {:else}
    <ol>
      {#each questions as item, index}
        <li class:free={!item.consumes_question}>
          <div class="question">
            <span class="index">问 {index + 1}</span>
            <p>{item.question}</p>
          </div>
          <div class="answer">
            {#if item.invalid}
              <strong>无效</strong>
              <span>{item.reason ?? "请换成能用是/否回答的问题"}</span>
            {:else if item.degraded}
              <strong>暂不可用</strong>
              <span>{item.reason ?? "这次没有消耗提问次数"}</span>
            {:else}
              <strong>{item.answer}</strong>
              {#if !item.consumes_question}
                <span>未消耗次数</span>
              {/if}
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .question-list {
    margin: 1.25rem 0;
  }
  .empty {
    margin: 0;
    color: var(--color-text-soft);
    font-size: 0.92rem;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  li {
    padding: 0.85rem 1rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-soft);
    border-radius: 6px;
  }
  li.free {
    border-style: dashed;
  }
  .question,
  .answer {
    display: flex;
    gap: 0.65rem;
    align-items: flex-start;
  }
  .question {
    margin-bottom: 0.45rem;
  }
  .index {
    flex: 0 0 auto;
    color: var(--color-primary);
    font-size: 0.78rem;
    font-weight: 600;
  }
  p {
    margin: 0;
  }
  .answer strong {
    flex: 0 0 auto;
    color: var(--color-text);
  }
  .answer span {
    color: var(--color-text-soft);
    font-size: 0.9rem;
  }
</style>
