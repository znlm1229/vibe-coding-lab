<script lang="ts">
  // T17: daily 分享按钮 — 复制文本到剪贴板
  // 格式: 猜历史人物 #N\n❓❓❓✅ 用了 3 条线索\nhttps://<domain>

  interface Props {
    dayIndex: number; // 第 N 题
    revealedCount: number; // 用了几条线索
    won: boolean;
    rescue: boolean; // 是否触发了求救
  }

  let { dayIndex, revealedCount, won, rescue }: Props = $props();
  let copied = $state(false);

  function buildShareText(): string {
    const totalSlots = 5; // 标准范围只展示 5 格
    let icons = "";
    if (!won) {
      icons = "❌".repeat(totalSlots);
    } else if (rescue) {
      // 求救 = 6/7 条都用了 + 猜中
      icons = "❓".repeat(totalSlots) + "🆘";
    } else {
      // 标准范围猜中
      const used = Math.min(revealedCount, totalSlots);
      icons = "❓".repeat(used - 1) + "✅" + "❓".repeat(totalSlots - used);
    }
    const url = typeof window !== "undefined" ? window.location.origin : "";
    return `猜历史人物 #${dayIndex + 1}\n${icons} ${won ? `用了 ${revealedCount} 条线索` : "未猜中"}\n${url}`;
  }

  async function share() {
    const text = buildShareText();
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
      setTimeout(() => (copied = false), 2500);
    } catch (e) {
      console.error("复制失败:", e);
      alert("复制失败，请手动复制：\n\n" + text);
    }
  }
</script>

<div class="share">
  <button onclick={share}>{copied ? "✅ 已复制到剪贴板" : "📋 分享成绩"}</button>
  <details>
    <summary>预览分享文本</summary>
    <pre>{buildShareText()}</pre>
  </details>
</div>

<style>
  .share {
    margin-top: 1rem;
  }
  button {
    padding: 0.6rem 1.3rem;
    background: var(--color-primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.95rem;
  }
  button:hover {
    background: var(--color-primary-dark);
  }
  details {
    margin-top: 0.6rem;
    font-size: 0.85rem;
    color: var(--color-text-soft);
  }
  pre {
    margin: 0.4rem 0 0;
    padding: 0.6rem;
    background: var(--color-bg-card);
    border-radius: 4px;
    white-space: pre-wrap;
    font-family: ui-monospace, monospace;
  }
</style>
