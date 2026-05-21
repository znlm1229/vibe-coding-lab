<script lang="ts">
  // 固定目标人物 = 诸葛亮（prototype 验证用，V1 实际从题库读）
  const TARGET = {
    name: "诸葛亮",
    aliases: ["孔明", "卧龙", "武侯", "诸葛武侯", "忠武"],
  };

  let userInput = $state("");
  let loading = $state(false);
  let result = $state<{ correct: boolean; reason: string } | null>(null);
  let error = $state<string | null>(null);
  let latency = $state<number | null>(null);

  async function submit() {
    if (!userInput.trim()) return;
    loading = true;
    error = null;
    result = null;
    latency = null;
    const t0 = performance.now();
    try {
      const r = await fetch("/api/check-answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: userInput, target: TARGET }),
      });
      latency = performance.now() - t0;
      if (!r.ok) {
        error = `HTTP ${r.status}: ${await r.text()}`;
      } else {
        result = await r.json();
      }
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }
</script>

<main>
  <h1>guess-figure prototype B</h1>
  <p>Stage 3 部署链路验证：SvelteKit + adapter-cloudflare + CF Pages Function + 云雾 LLM 调用</p>

  <section class="target">
    <strong>固定目标人物：</strong>{TARGET.name}<br />
    <strong>异称表（写死）：</strong>{TARGET.aliases.join(" / ")}
  </section>

  <section class="form">
    <label>
      你的猜测：
      <input
        bind:value={userInput}
        placeholder="试试：孔明 / 卧龙 / 诸葛丞相 / 曹操 / 诸葛梁..."
        onkeydown={(e) => e.key === "Enter" && submit()}
      />
    </label>
    <button onclick={submit} disabled={loading || !userInput.trim()}>
      {loading ? "调用 LLM 中..." : "提交"}
    </button>
  </section>

  {#if error}
    <pre class="error">❌ {error}</pre>
  {/if}

  {#if result}
    <section class="result {result.correct ? 'ok' : 'no'}">
      <p>
        <strong>{result.correct ? "✅ 算对" : "❌ 不算"}</strong>
        {#if latency !== null}<small>（{latency.toFixed(0)}ms）</small>{/if}
      </p>
      <p>{result.reason}</p>
    </section>
  {/if}

  <section class="test-cases">
    <h3>测试用例参考</h3>
    <ul>
      <li><code>孔明</code>、<code>卧龙</code>、<code>武侯</code> → 异称表内 → ✅</li>
      <li><code>诸葛丞相</code>、<code>诸葛孔明</code> → 异称表外但 LLM 能识别 → ✅</li>
      <li><code>诸葛</code>（仅姓氏） → ❌（信息不足）</li>
      <li><code>诸葛梁</code>（错别字） → ❌（错字不容忍）</li>
      <li><code>曹操</code> → ❌（不同人物）</li>
    </ul>
  </section>
</main>

<style>
  main {
    max-width: 720px;
    margin: 2rem auto;
    padding: 1.5rem;
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
  }
  h1 {
    font-size: 1.6rem;
    margin-bottom: 0.25rem;
  }
  .target {
    background: #f5f5f5;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    margin: 1rem 0;
    font-size: 0.9rem;
  }
  .form {
    display: flex;
    gap: 0.5rem;
    margin: 1.5rem 0;
  }
  label {
    flex: 1;
    display: flex;
    flex-direction: column;
    font-size: 0.85rem;
    color: #666;
  }
  input {
    padding: 0.5rem;
    font-size: 1rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  button {
    align-self: flex-end;
    padding: 0.5rem 1.25rem;
    font-size: 1rem;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  button:disabled {
    background: #ccc;
    cursor: not-allowed;
  }
  .result {
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem 0;
  }
  .result.ok {
    background: #ecfdf5;
    border-left: 4px solid #10b981;
  }
  .result.no {
    background: #fef2f2;
    border-left: 4px solid #ef4444;
  }
  .error {
    background: #fef2f2;
    color: #991b1b;
    padding: 0.75rem;
    border-radius: 4px;
    white-space: pre-wrap;
    font-size: 0.85rem;
  }
  .test-cases {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid #eee;
    font-size: 0.85rem;
    color: #666;
  }
  code {
    background: #eef;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-family: ui-monospace, monospace;
  }
</style>
