#!/usr/bin/env python3
"""
Stage 3 Prototype: LLM 计费实测脚本（任务 002-account-rate-limit）。

目的:
  调云雾中转 gemini-3.1-flash-lite N 次（默认 100），形态与 src/routes/api/check-answer/+server.ts
  完全一致（max_tokens=300, temperature=0.1），统计 token 用量与延迟。
  实测数据用于回填 SPEC 的 V (每日全局 LLM 预算) 与 X (单 user 日 LLM 上限) 阈值。

跑法:
  cd projects/guess-figure
  source venv/Scripts/activate   # Windows; Linux/Mac 用 source venv/bin/activate
  python scripts/measure_llm_cost.py --count 100

  快速 sanity check 跑 5 次:
  python scripts/measure_llm_cost.py --count 5

输出:
  - 控制台: 实时进度 + 最终统计
  - scripts/logs/llm_cost_<timestamp>.json: 每次调用的完整记录
  - 末尾打印 V/X 阈值的建议公式（用户根据日预算容忍消费回填 SPEC）

不做的事:
  - 不并发（云雾自身限流未知，串行最稳；100 次 × ~4s = ~7 分钟）
  - 不验证 LLM 答案的 correct/wrong（只测调用形态 + token 用量，不评准确度）
  - 不写本地缓存（这正是要测的：每次都真打 LLM）
"""

import argparse
import json
import logging
import os
import random
import statistics
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
FIGURES_JSON = PROJECT_ROOT / "src" / "lib" / "data" / "figures.json"
LOG_DIR = Path(__file__).parent / "logs"

LLM_API_KEY = os.environ.get("YUNWU_API_KEY")
LLM_BASE_URL = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")
if not LLM_BASE_URL.endswith("/v1"):
    LLM_BASE_URL = LLM_BASE_URL + "/v1"
LLM_MODEL_DEFAULT = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
LLM_URL = f"{LLM_BASE_URL}/chat/completions"

# 与 check-answer/+server.ts 一致
LLM_MAX_TOKENS = 300
LLM_TEMPERATURE = 0.1
LLM_TIMEOUT_SEC = 10

# 用于构造"非 exact match 但语义上合理"的猜测输入（强制 LLM 介入而非 exact 短路）。
# 这些后缀附在 figure.name 上，模拟用户输入"诸葛丞相 / 李太白 / 曹丞相"等。
GUESS_SUFFIXES = ["丞相", "先生", "大将军", "公子", "陛下", "夫子", "侯爷"]
GUESS_PREFIXES = ["", "我猜是", "应该是", "可能是"]


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger("measure_llm_cost")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def load_figures() -> list[dict]:
    """读题库 figures.json。"""
    if not FIGURES_JSON.exists():
        raise FileNotFoundError(f"题库不存在: {FIGURES_JSON}（先确保 V1 题库已 merge）")
    with FIGURES_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def build_test_pairs(figures: list[dict], count: int) -> list[tuple[dict, str]]:
    """构造 N 个 (figure, guess_input) 测试对，确保每个 prompt 唯一。"""
    pairs: list[tuple[dict, str]] = []
    rng = random.Random(42)  # 固定 seed，保结果可复现
    while len(pairs) < count:
        fig = rng.choice(figures)
        prefix = rng.choice(GUESS_PREFIXES)
        suffix = rng.choice(GUESS_SUFFIXES)
        guess = f"{prefix}{fig['name'][0]}{suffix}"  # 取姓 + 称谓后缀（如 "诸丞相" / "我猜是李先生"）
        pairs.append((fig, guess))
    return pairs


def build_prompt(input_str: str, target_name: str, aliases: list[str]) -> str:
    """与 check-answer/+server.ts line 34-50 完全一致的 prompt。"""
    return f"""你是历史人物姓名识别助手。判断用户输入是否在指代目标人物。

目标人物：{target_name}
已知异称（字 / 号 / 谥号 / 庙号 / 别号）：{"、".join(aliases)}

用户输入："{input_str}"

判定规则：
- 用户输入是本名 / 字 / 号 / 谥号 / 庙号 / 别号 → YES
- 用户输入是异称的常见组合或简写（如"诸葛丞相"指诸葛亮、"曹孟德"指曹操）→ YES
- 用户输入仅是姓氏（如"诸葛"）→ NO（太宽泛）
- 用户输入仅是单名（如"亮"）→ NO（信息不足）
- 用户输入是错别字 → NO（不容忍错字）
- 不确定 → NO

请严格输出 JSON：{{"correct": true|false, "reason": "<一句话理由>"}}
不要任何 markdown 代码块标记或额外说明文字。"""


def call_llm(prompt: str, model: str) -> dict:
    """单次 LLM 调用。返回含 usage + latency + raw response 的 dict。"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    t0 = time.monotonic()
    try:
        resp = requests.post(LLM_URL, json=payload, headers=headers, timeout=LLM_TIMEOUT_SEC)
        latency_ms = round((time.monotonic() - t0) * 1000)
    except requests.RequestException as e:
        return {
            "ok": False,
            "error": f"network: {e}",
            "latency_ms": round((time.monotonic() - t0) * 1000),
        }

    if not resp.ok:
        return {
            "ok": False,
            "error": f"http {resp.status_code}: {resp.text[:200]}",
            "latency_ms": latency_ms,
        }

    data = resp.json()
    usage = data.get("usage", {}) or {}
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {
        "ok": True,
        "latency_ms": latency_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "content_snippet": (content or "")[:80],
    }


def main():
    if not LLM_API_KEY:
        print("❌ 缺 YUNWU_API_KEY 环境变量（检查项目根 .env）", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="实测云雾 LLM 调用计费（任务 002）")
    parser.add_argument("--count", type=int, default=100, help="调用次数（默认 100，sanity check 用 5）")
    parser.add_argument("--model", default=LLM_MODEL_DEFAULT, help=f"LLM 模型（默认 {LLM_MODEL_DEFAULT}）")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认 scripts/logs/llm_cost_<ts>.json）")
    parser.add_argument("--daily-budget-yuan", type=float, default=5.0,
                        help="你愿意每天为 LLM 花的人民币上限（默认 ¥5），用于回填 V 阈值")
    args = parser.parse_args()

    logger = setup_logging()

    if not FIGURES_JSON.exists():
        print(f"❌ 题库不存在: {FIGURES_JSON}", file=sys.stderr)
        sys.exit(1)

    figures = load_figures()
    pairs = build_test_pairs(figures, args.count)
    logger.info(f"准备 {len(pairs)} 次调用 (model={args.model}, max_tokens={LLM_MAX_TOKENS})")
    logger.info(f"  题库 figures: {len(figures)} 人")
    logger.info(f"  云雾 endpoint: {LLM_URL}")

    output_path = Path(args.output) if args.output else LOG_DIR / f"llm_cost_{time.strftime('%Y%m%d_%H%M%S')}.json"
    LOG_DIR.mkdir(exist_ok=True)

    records = []
    t_start = time.monotonic()
    for i, (fig, guess) in enumerate(pairs, start=1):
        prompt = build_prompt(guess, fig["name"], fig.get("aliases", []))
        result = call_llm(prompt, args.model)
        result["call_index"] = i
        result["figure_name"] = fig["name"]
        result["guess_input"] = guess
        result["prompt_len_chars"] = len(prompt)
        records.append(result)

        ok_mark = "✓" if result["ok"] else "✗"
        token_info = (
            f"in={result.get('prompt_tokens')} out={result.get('completion_tokens')} total={result.get('total_tokens')}"
            if result["ok"] else f"err: {result.get('error', '?')[:60]}"
        )
        logger.info(f"[{i:>3}/{len(pairs)}] {ok_mark} {result['latency_ms']:>5}ms {fig['name']:<5} ← \"{guess}\"  | {token_info}")

    t_elapsed = time.monotonic() - t_start

    successes = [r for r in records if r["ok"]]
    failures = [r for r in records if not r["ok"]]

    if not successes:
        logger.error("⚠️ 全部调用失败，无法统计 token 用量")
        with output_path.open("w", encoding="utf-8") as f:
            json.dump({"args": vars(args), "records": records, "elapsed_sec": t_elapsed}, f,
                      ensure_ascii=False, indent=2)
        logger.info(f"原始记录: {output_path}")
        sys.exit(2)

    prompt_tokens = [r.get("prompt_tokens") for r in successes if r.get("prompt_tokens") is not None]
    completion_tokens = [r.get("completion_tokens") for r in successes if r.get("completion_tokens") is not None]
    total_tokens = [r.get("total_tokens") for r in successes if r.get("total_tokens") is not None]
    latencies = [r["latency_ms"] for r in successes]

    summary = {
        "calls_total": len(records),
        "calls_ok": len(successes),
        "calls_failed": len(failures),
        "elapsed_sec": round(t_elapsed, 2),
        "avg_latency_ms": round(statistics.mean(latencies)) if latencies else None,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[-1]) if len(latencies) >= 20 else None,
        "prompt_tokens": {
            "sum": sum(prompt_tokens),
            "mean": round(statistics.mean(prompt_tokens), 1) if prompt_tokens else None,
            "min": min(prompt_tokens) if prompt_tokens else None,
            "max": max(prompt_tokens) if prompt_tokens else None,
        },
        "completion_tokens": {
            "sum": sum(completion_tokens),
            "mean": round(statistics.mean(completion_tokens), 1) if completion_tokens else None,
            "min": min(completion_tokens) if completion_tokens else None,
            "max": max(completion_tokens) if completion_tokens else None,
        },
        "total_tokens": {
            "sum": sum(total_tokens),
            "mean": round(statistics.mean(total_tokens), 1) if total_tokens else None,
        },
    }

    # 打印总结
    print()
    print("=" * 70)
    print("LLM 计费实测总结 (Stage 3 Prototype)")
    print("=" * 70)
    print(f"调用次数:     {summary['calls_total']} (成功 {summary['calls_ok']}, 失败 {summary['calls_failed']})")
    print(f"总耗时:       {summary['elapsed_sec']}s")
    print(f"平均延迟:     {summary['avg_latency_ms']}ms  (p95: {summary['p95_latency_ms']}ms)")
    print(f"Prompt tokens 累计: {summary['prompt_tokens']['sum']}  (均值 {summary['prompt_tokens']['mean']}/次)")
    print(f"Completion tokens 累计: {summary['completion_tokens']['sum']}  (均值 {summary['completion_tokens']['mean']}/次)")
    print(f"Total tokens 累计: {summary['total_tokens']['sum']}  (均值 {summary['total_tokens']['mean']}/次)")
    print()
    print("🪙 接下来手动操作（脚本不知云雾计费单价）:")
    print(f"   1. 登录云雾 console, 查看本次实测前后的账户余额差额 ΔY (元)")
    print(f"   2. 单次调用成本 ≈ ΔY / {summary['calls_ok']} 元/call")
    print(f"   3. 你设定的日预算: ¥{args.daily_budget_yuan} → V 阈值 ≈ {args.daily_budget_yuan} / 单次成本")
    print(f"   4. X 阈值（单 user 日上限）= V 的 1/N 比例，N 是 \"重度玩家假设占比\" (建议 N=50~100)")
    print()
    print(f"详细记录: {output_path}")
    print("=" * 70)

    # 写文件
    with output_path.open("w", encoding="utf-8") as f:
        json.dump({
            "args": vars(args),
            "summary": summary,
            "records": records,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
