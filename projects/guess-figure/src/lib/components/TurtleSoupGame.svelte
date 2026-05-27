<script lang="ts">
  import { onMount } from "svelte";
  import type { TurtleAnswerApiResponse, TurtleQuestionApiResponse } from "$lib/types";
  import {
    applyTurtleAnswerResult,
    applyTurtleQuestionResult,
    TURTLE_SOUP_MAX_ANSWER_ATTEMPTS,
    TURTLE_SOUP_MAX_QUESTIONS,
    type TurtleSoupRound,
  } from "$lib/turtle-soup-state";
  import TurtleQuestionList from "$lib/components/TurtleQuestionList.svelte";

  interface Props {
    initialRound: TurtleSoupRound;
  }

  let { initialRound }: Props = $props();

  let round = $state((() => cloneRound(initialRound))());
  let sessionReady = $state(false);
  let sessionError = $state<string | null>(null);
  let questionText = $state("");
  let answerText = $state("");
  let asking = $state(false);
  let answering = $state(false);
  let lastMessage = $state<string | null>(null);

  let questionsRemaining = $derived(TURTLE_SOUP_MAX_QUESTIONS - round.question_count);
  let answersRemaining = $derived(TURTLE_SOUP_MAX_ANSWER_ATTEMPTS - round.answer_attempts_used);

  onMount(() => {
    void createSession();
  });

  async function createSession() {
    sessionReady = false;
    sessionError = null;
    try {
      const response = await postJson("/api/turtle/session", {
        mode: "standalone",
        session_id: round.session_id,
        figure_id: round.figure.id,
      });
      if (!response.ok) {
        throw new Error(await readError(response, "创建会话失败"));
      }
      sessionReady = true;
    } catch (cause) {
      sessionError = cause instanceof Error ? cause.message : "创建会话失败";
    }
  }

  async function askQuestion() {
    const question = questionText.trim();
    if (!question || !round.can_ask_question || asking) return;

    asking = true;
    lastMessage = null;
    try {
      const response = await postJson("/api/turtle/question", {
        mode: "standalone",
        figure_id: round.figure.id,
        question,
      });
      if (!response.ok) {
        throw new Error(await readError(response, "提问失败"));
      }
      const body = (await response.json()) as TurtleQuestionApiResponse;
      round = applyTurtleQuestionResult(round, question, body);
      if (!body.invalid) questionText = "";
      if (body.invalid || body.degraded) {
        lastMessage = body.reason ?? "这次没有消耗提问次数";
      }
    } catch (cause) {
      lastMessage = cause instanceof Error ? cause.message : "提问失败";
    } finally {
      asking = false;
    }
  }

  async function submitAnswer() {
    const answer = answerText.trim();
    if (!answer || !round.can_submit_answer || answering || !sessionReady) return;

    answering = true;
    lastMessage = null;
    try {
      const response = await postJson("/api/turtle/answer", {
        mode: "standalone",
        session_id: round.session_id,
        figure_id: round.figure.id,
        answer,
        question_count: round.question_count,
      });
      if (!response.ok) {
        throw new Error(await readError(response, "提交答案失败"));
      }
      const body = (await response.json()) as TurtleAnswerApiResponse;
      round = applyTurtleAnswerResult(round, body);
      answerText = "";
      if (round.status === "won") {
        lastMessage = "猜中了。";
      } else if (round.status === "lost") {
        lastMessage = "答案机会已用完。";
      } else {
        lastMessage = `不对，还剩 ${answersRemaining} 次答案机会。`;
      }
    } catch (cause) {
      lastMessage = cause instanceof Error ? cause.message : "提交答案失败";
    } finally {
      answering = false;
    }
  }

  function handleQuestionKeydown(event: KeyboardEvent) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    void askQuestion();
  }

  function handleAnswerKeydown(event: KeyboardEvent) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void submitAnswer();
  }

  async function postJson(url: string, body: unknown): Promise<Response> {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function readError(response: Response, fallback: string): Promise<string> {
    try {
      const body = (await response.json()) as { message?: string };
      return body.message ?? `${fallback} (HTTP ${response.status})`;
    } catch {
      return `${fallback} (HTTP ${response.status})`;
    }
  }

  function cloneRound(source: TurtleSoupRound): TurtleSoupRound {
    return {
      ...source,
      questions: [...source.questions],
    };
  }
</script>

<section class="game">
  <div class="opening">
    <span class="label">汤面</span>
    <p>{round.turtle_intro}</p>
  </div>

  <div class="meters" aria-label="剩余次数">
    <span>提问 <strong>{round.question_count}/{TURTLE_SOUP_MAX_QUESTIONS}</strong></span>
    <span>答案 <strong>{round.answer_attempts_used}/{TURTLE_SOUP_MAX_ANSWER_ATTEMPTS}</strong></span>
  </div>

  {#if sessionError}
    <p class="notice error">{sessionError}</p>
  {:else if !sessionReady}
    <p class="notice">正在开局...</p>
  {/if}

  <TurtleQuestionList questions={round.questions} />

  {#if round.status === "playing"}
    <section class="panel">
      <h2>提问</h2>
      <textarea
        bind:value={questionText}
        disabled={!round.can_ask_question || asking}
        rows="3"
        placeholder="例如：他是不是皇帝？"
        onkeydown={handleQuestionKeydown}
      ></textarea>
      <div class="row">
        <span>{questionsRemaining} 次可用</span>
        <button onclick={askQuestion} disabled={!questionText.trim() || !round.can_ask_question || asking}>
          {asking ? "提问中..." : "提问"}
        </button>
      </div>
    </section>

    <section class="panel">
      <h2>答案</h2>
      <input
        type="text"
        bind:value={answerText}
        disabled={!sessionReady || !round.can_submit_answer || answering}
        placeholder="输入你猜的人物名"
        autocomplete="off"
        onkeydown={handleAnswerKeydown}
      />
      <div class="row">
        <span>{answersRemaining} 次可用</span>
        <button
          onclick={submitAnswer}
          disabled={!answerText.trim() || !sessionReady || !round.can_submit_answer || answering}
        >
          {answering ? "判定中..." : "提交答案"}
        </button>
      </div>
    </section>
  {:else}
    <section class="reveal {round.status}">
      {#if round.status === "won"}
        <h2>猜中了</h2>
      {:else}
        <h2>答案揭晓</h2>
      {/if}
      <p class="answer-name">{round.figure.name}</p>
      {#if round.figure.aliases.length > 0}
        <p class="aliases">别名：{round.figure.aliases.join("、")}</p>
      {/if}
      <a href={round.figure.wiki_url} target="_blank" rel="noopener">查看资料</a>
    </section>
  {/if}

  {#if lastMessage}
    <p class="notice">{lastMessage}</p>
  {/if}
</section>

<style>
  .game {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .opening {
    padding: 1.4rem 1.5rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
  }
  .label {
    display: block;
    color: var(--color-primary);
    font-size: 0.8rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
  }
  .opening p {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.8rem;
    line-height: 1.4;
  }
  .meters {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .meters span {
    padding: 0.45rem 0.7rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-soft);
    border-radius: 6px;
    font-size: 0.9rem;
  }
  .meters strong {
    color: var(--color-primary);
  }
  .panel {
    padding: 1rem;
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-soft);
    border-radius: 8px;
  }
  h2 {
    margin: 0 0 0.7rem;
    font-size: 1.05rem;
  }
  textarea,
  input {
    width: 100%;
    padding: 0.7rem 0.85rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: white;
    color: var(--color-text);
    font-size: 1rem;
    resize: vertical;
  }
  textarea:focus,
  input:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: -1px;
  }
  .row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    margin-top: 0.75rem;
    color: var(--color-text-soft);
    font-size: 0.9rem;
  }
  button {
    min-width: 6.5rem;
    padding: 0.58rem 1rem;
    border: none;
    border-radius: 4px;
    background: var(--color-primary);
    color: white;
    cursor: pointer;
    font-size: 0.95rem;
  }
  button:disabled {
    background: var(--color-border);
    cursor: not-allowed;
  }
  .notice {
    margin: 0;
    padding: 0.75rem 0.9rem;
    border-left: 3px solid var(--color-primary);
    background: var(--color-info-bg);
    color: var(--color-info);
    border-radius: 4px;
  }
  .notice.error {
    border-left-color: var(--color-error-border);
    background: var(--color-error-bg);
    color: var(--color-error);
  }
  .reveal {
    padding: 1.2rem;
    border-radius: 8px;
    border: 1px solid var(--color-border);
    background: var(--color-bg-card);
  }
  .reveal.won {
    border-color: var(--color-success-border);
    background: var(--color-success-bg);
  }
  .reveal.lost {
    border-color: var(--color-error-border);
    background: var(--color-error-bg);
  }
  .answer-name {
    margin: 0.5rem 0;
    font-size: 1.6rem;
    font-weight: 700;
  }
  .aliases {
    margin: 0 0 0.5rem;
    color: var(--color-text-soft);
  }
  @media (max-width: 640px) {
    .opening p {
      font-size: 1.55rem;
    }
    .row {
      align-items: stretch;
      flex-direction: column;
      gap: 0.6rem;
    }
    button {
      width: 100%;
    }
  }
</style>
