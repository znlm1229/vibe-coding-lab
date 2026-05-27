<script lang="ts">
  import type { TurtleQuestionApiResponse } from "$lib/types";

  type TurtleRecord = {
    question: string;
    answer?: string;
    message?: string;
    tone: "ok" | "warn" | "err";
  };

  type Props = {
    figureId: string;
    gameId: string;
    questionsRemaining: number;
    canAskQuestion: boolean;
    onQuestionConsumed: () => void;
  };

  let { figureId, gameId, questionsRemaining, canAskQuestion, onQuestionConsumed }: Props = $props();

  let question = $state("");
  let asking = $state(false);
  let records = $state<TurtleRecord[]>([]);
  let embeddedMarked = $state(false);

  async function markEmbeddedUsed() {
    if (embeddedMarked) return;
    embeddedMarked = true;
    try {
      const response = await fetch("/api/turtle/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "embedded",
          game_id: gameId,
          figure_id: figureId,
        }),
      });
      if (!response.ok) {
        console.warn("[turtle/answer] 记录嵌入式海龟汤使用失败（不阻塞 UI）:", response.status);
      }
    } catch (error) {
      console.warn("[turtle/answer] 记录嵌入式海龟汤使用失败（不阻塞 UI）:", error);
    }
  }

  async function submitQuestion() {
    const trimmed = question.trim();
    if (!trimmed || asking || !canAskQuestion) return;

    asking = true;
    try {
      const response = await fetch("/api/turtle/question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          figure_id: figureId,
          game_id: gameId,
          question: trimmed,
          mode: "embedded",
        }),
      });

      if (!response.ok) {
        records = [
          ...records,
          { question: trimmed, message: "提问失败，请稍后重试。", tone: "err" },
        ];
        return;
      }

      const result = (await response.json()) as TurtleQuestionApiResponse;
      if (result.consumes_question && !result.invalid && !result.degraded && !result.network_error) {
        onQuestionConsumed();
        await markEmbeddedUsed();
        question = "";
      }

      records = [...records, toRecord(trimmed, result)];
    } catch (error) {
      console.warn("[turtle/question] 嵌入式提问失败:", error);
      records = [...records, { question: trimmed, message: "网络异常，本次不扣次数。", tone: "err" }];
    } finally {
      asking = false;
    }
  }

  function toRecord(input: string, result: TurtleQuestionApiResponse): TurtleRecord {
    if (result.invalid) {
      return {
        question: input,
        message: result.reason ?? "请改成能用“是/否”回答的问题。",
        tone: "warn",
      };
    }
    if (result.degraded || result.network_error) {
      return {
        question: input,
        message: result.reason ?? "海龟汤问答暂时不可用，本次不扣次数。",
        tone: "warn",
      };
    }
    return {
      question: input,
      answer: result.answer ?? "无关",
      tone: "ok",
    };
  }
</script>

<section class="turtle-panel" aria-label="海龟汤辅助">
  <div class="panel-head">
    <div>
      <h2>海龟汤辅助</h2>
      <p>可问最多 5 个是/否问题；使用后本局得分记为 0。</p>
    </div>
    <span class="counter">剩余 {questionsRemaining}/5</span>
  </div>

  <form class="ask-row" onsubmit={(event) => { event.preventDefault(); submitQuestion(); }}>
    <input
      bind:value={question}
      disabled={asking || !canAskQuestion}
      maxlength="80"
      placeholder={canAskQuestion ? "例如：此人是皇帝吗？" : "本局提问次数已用完"}
      aria-label="海龟汤问题"
    />
    <button type="submit" disabled={asking || !canAskQuestion || !question.trim()}>
      {asking ? "询问中" : "提问"}
    </button>
  </form>

  {#if records.length > 0}
    <div class="records" aria-live="polite">
      {#each records as record}
        <article class="record record-{record.tone}">
          <p class="question">问：{record.question}</p>
          {#if record.answer}
            <p class="answer">答：{record.answer}</p>
          {:else}
            <p class="message">{record.message}</p>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
</section>

<style>
  .turtle-panel {
    margin: 0 0 1.4rem;
    padding: 1rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-accent);
    border-radius: 6px;
  }

  .panel-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    margin-bottom: 0.8rem;
  }

  h2 {
    margin: 0;
    font-size: 1rem;
  }

  .panel-head p {
    margin: 0.2rem 0 0;
    color: var(--color-text-soft);
    font-size: 0.88rem;
  }

  .counter {
    flex: 0 0 auto;
    padding: 0.15rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    color: var(--color-primary);
    font-size: 0.82rem;
    font-weight: 700;
    white-space: nowrap;
  }

  .ask-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.6rem;
  }

  input {
    width: 100%;
    min-width: 0;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--color-border);
    background: #fffdf8;
    color: var(--color-text);
    font-size: 0.95rem;
  }

  button {
    min-width: 5rem;
    padding: 0.55rem 0.9rem;
    border: 0;
    border-radius: 4px;
    background: var(--color-accent);
    color: #fff;
    font-size: 0.95rem;
    cursor: pointer;
    white-space: nowrap;
  }

  button:disabled,
  input:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }

  .records {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    margin-top: 0.8rem;
  }

  .record {
    padding: 0.55rem 0.7rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .record-ok {
    background: var(--color-info-bg);
  }

  .record-warn {
    background: var(--color-warning-bg);
  }

  .record-err {
    background: var(--color-error-bg);
  }

  .question,
  .answer,
  .message {
    margin: 0;
  }

  .answer,
  .message {
    color: var(--color-text-soft);
  }

  @media (max-width: 520px) {
    .panel-head {
      flex-direction: column;
      gap: 0.45rem;
    }

    .ask-row {
      grid-template-columns: 1fr;
    }

    button {
      width: 100%;
    }
  }
</style>
