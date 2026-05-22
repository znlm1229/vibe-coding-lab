<script lang="ts">
  // T7: 答案输入框 + 中文 IME 处理
  //
  // 关键 bug 预防（SPEC AC14 + grill-me §R3）：
  // 中文输入法 (IME) composition 期间按 Enter 应该是"确认拼音/词组"，
  // 不应该提交。必须监听 compositionstart / compositionend 区分。
  //
  // 用法:
  //   <AnswerInput
  //     bind:value
  //     placeholder="试试输入..."
  //     disabled={loading}
  //     onsubmit={(text) => handleSubmit(text)}
  //   />

  interface Props {
    value: string;
    placeholder?: string;
    disabled?: boolean;
    onsubmit: (text: string) => void;
  }

  let {
    value = $bindable(""),
    placeholder = "输入你的答案...",
    disabled = false,
    onsubmit,
  }: Props = $props();

  // composition 状态：true = 输入法编辑中（拼音半成品），按 Enter 不应该提交
  let composing = $state(false);

  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== "Enter") return;
    if (composing) return; // IME 编辑中不触发
    e.preventDefault();
    submit();
  }

  function submit() {
    const text = value.trim();
    if (!text) return;
    onsubmit(text);
  }
</script>

<div class="input-row">
  <input
    type="text"
    bind:value
    {placeholder}
    {disabled}
    autocomplete="off"
    autocorrect="off"
    autocapitalize="off"
    spellcheck="false"
    oncompositionstart={() => (composing = true)}
    oncompositionend={() => (composing = false)}
    onkeydown={handleKeydown}
  />
  <button
    type="button"
    onclick={submit}
    disabled={disabled || !value.trim()}
  >
    提交
  </button>
</div>

<style>
  .input-row {
    display: flex;
    gap: 0.5rem;
    width: 100%;
  }
  input {
    flex: 1;
    padding: 0.65rem 0.85rem;
    font-size: 1rem;
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-family: inherit;
  }
  input:focus {
    outline: 2px solid #2563eb;
    outline-offset: -1px;
  }
  input:disabled {
    background: #f3f4f6;
    cursor: not-allowed;
  }
  button {
    padding: 0.65rem 1.25rem;
    font-size: 0.95rem;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  button:disabled {
    background: #cbd5e1;
    cursor: not-allowed;
  }
</style>
