<script lang="ts">
  import TurtleSoupGame from "$lib/components/TurtleSoupGame.svelte";
  import type { PageData } from "./$types";

  interface Props {
    data: PageData;
  }

  let { data }: Props = $props();
</script>

<svelte:head>
  <title>海龟汤 - 猜历史人物</title>
</svelte:head>

<main>
  <header>
    <h1>海龟汤</h1>
    <p class="subtitle">一条汤面，十五次提问，三次作答。</p>
  </header>

  <TurtleSoupGame initialRound={data.initialRound} />
</main>

<style>
  main {
    max-width: 720px;
    margin: 2rem auto;
    padding: 1.5rem;
    color: var(--color-text);
    line-height: 1.7;
  }
  header {
    margin-bottom: 1.5rem;
  }
  h1 {
    margin: 0;
    font-size: 1.8rem;
  }
  .subtitle {
    margin: 0.3rem 0 0;
    color: var(--color-text-soft);
    font-size: 0.95rem;
  }
</style>
