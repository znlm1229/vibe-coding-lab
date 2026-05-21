#!/usr/bin/env python3
"""
独立连通性测试 — 验证云雾 API 配置正确。

只做一件事：调 GET /models 列出可用模型。10 秒超时。

跑法：python test_connectivity.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.environ.get("YUNWU_API_KEY")
base = (os.environ.get("YUNWU_BASE_URL") or "https://yunwu.ai/v1").rstrip("/")

# 测多种常见 endpoint 变体（按可能性排序）
# 关键发现：云雾的 web 域名是 yunwu.ai，但 logo 资源来自 wlai.vip
# 暗示实际 API 域名可能是 wlai.vip 系列（中转站常见的"web/API 分域"架构）
CANDIDATES = [
    base if base.endswith("/v1") else base + "/v1",
    "https://yunwu.ai/v1",
    "https://api.yunwu.ai/v1",
    "https://api.wlai.vip/v1",
    "https://wlai.vip/v1",
    "https://yunwu.ai/api/v1",
]
# 去重保序
seen = set()
CANDIDATES = [u for u in CANDIDATES if not (u in seen or seen.add(u))]

print(f"当前 .env: base_url={base}, key={'(set)' if key else '(MISSING)'}\n")

if not key:
    print("❌ YUNWU_API_KEY 未设置，先填 .env")
    raise SystemExit(1)

for url in CANDIDATES:
    print(f"━━━ 测 {url}/models ━━━")
    try:
        r = requests.get(
            f"{url}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        ct = r.headers.get("Content-Type", "")
        print(f"  HTTP {r.status_code}, Content-Type: {ct}")

        # 关键校验：必须是 JSON 响应才是真 API（HTML 都是命中 web 页面）
        if "html" in ct.lower() or r.text.lstrip().startswith("<"):
            print(f"  ⚠️ 响应是 HTML（命中 web 页面，不是 API）- 跳过")
            print()
            continue

        if r.status_code != 200:
            print(f"  响应前 400 字: {r.text[:400]}")
            print()
            continue

        # 尝试解析 JSON
        try:
            data = r.json()
        except ValueError:
            print(f"  ⚠️ 200 但非 JSON: {r.text[:300]}")
            print()
            continue

        print(f"  ✅ 真 API 响应！响应前 400 字: {r.text[:400]}")
        print(f"\n✅ 这个 endpoint 通了！把 .env 的 YUNWU_BASE_URL 改成: {url}")
        # 挑 DeepSeek 相关模型
        models = data.get("data") or data.get("models") or []
        deepseek = [
            m.get("id") if isinstance(m, dict) else m
            for m in models
            if "deepseek" in (m.get("id", "") if isinstance(m, dict) else str(m)).lower()
        ]
        if deepseek:
            print(f"   找到的 DeepSeek 模型: {deepseek[:10]}")
            print(f"   把 .env 的 LLM_MODEL 改成上面其中之一（V1 推荐 deepseek-chat 或 deepseek-v3 类）")
        else:
            print(f"   未在模型列表里找到 deepseek 关键字 - 全部模型 (前 10): {[m.get('id') if isinstance(m, dict) else m for m in models[:10]]}")
        break
    except requests.exceptions.Timeout:
        print(f"  ❌ 10 秒超时")
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ 连接失败: {str(e)[:200]}")
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {str(e)[:200]}")
    print()

else:
    # /models 全失败 - 直接测 POST /chat/completions（云雾官方推荐的 endpoint）
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("所有 /models 都不通 - 直接测 POST /chat/completions")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 试几个模型名候选（云雾文档常见标识）
    MODEL_CANDIDATES = [
        os.environ.get("LLM_MODEL") or "deepseek-chat",
        "deepseek-chat",
        "deepseek-v3",
        "deepseek-v3-chat",
        "deepseek-reasoner",
    ]
    seen_m = set()
    MODEL_CANDIDATES = [m for m in MODEL_CANDIDATES if m and not (m in seen_m or seen_m.add(m))]

    chat_url = "https://yunwu.ai/v1/chat/completions"
    print(f"\n测试 URL: {chat_url}")

    for model in MODEL_CANDIDATES:
        print(f"\n--- 模型: {model} ---")
        try:
            r = requests.post(
                chat_url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "回复一个字: OK"}],
                    "max_tokens": 10,
                },
                timeout=30,
            )
            ct = r.headers.get("Content-Type", "")
            print(f"  HTTP {r.status_code}, Content-Type: {ct}")
            print(f"  响应前 500 字: {r.text[:500]}")

            if r.status_code == 200 and "json" in ct.lower():
                try:
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        print(f"\n  ✅ 成功！模型 '{model}' 可用，回复: {content!r}")
                        print(f"\n把 .env 改成:")
                        print(f"  YUNWU_BASE_URL=https://yunwu.ai/v1")
                        print(f"  LLM_MODEL={model}")
                        break
                except Exception as e:
                    print(f"  解析失败: {e}")
        except requests.exceptions.Timeout:
            print(f"  ❌ 30 秒超时（云雾这个 endpoint 可能挂了或被限速）")
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {str(e)[:200]}")

print("\n如果以上全失败：去云雾控制台找'API 接入'文档页，把 curl 示例完整贴给 AI。")
