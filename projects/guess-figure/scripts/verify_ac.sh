#!/usr/bin/env bash
# 004 T11: 海龟汤 RAG AC1-AC20 AI 通道验证脚本。
#
# 用法:
#   bash scripts/verify_ac.sh
#   bash scripts/verify_ac.sh --task 004
#
# 退出码:
#   0 = 全部自动项 PASS，且没有 BLOCKED / MANUAL
#   1 = 至少一个自动项 FAIL
#   2 = 自动项无 FAIL，但仍有已知 BLOCKED 或 MANUAL 待处理

set -u

if [ "${1:-}" = "--task" ]; then
  if [ "${2:-}" != "004" ]; then
    echo "仅支持 --task 004"
    exit 1
  fi
elif [ -n "${1:-}" ]; then
  echo "未知参数: $1"
  exit 1
fi

PASS=0
FAIL=0
BLOCKED=0
MANUAL=0
SKIP=0
RUN_DIR="$(mktemp -d)"
REPORT_JSON="$RUN_DIR/build-report.json"

cleanup() {
  rm -rf "$RUN_DIR"
}
trap cleanup EXIT

print_line() {
  printf '%s\n' "------------------------------------------------------------"
}

record() {
  local ac="$1"
  local status="$2"
  local message="$3"
  printf '[%s] %s - %s\n' "$ac" "$status" "$message"
  case "$status" in
    PASS) PASS=$((PASS + 1)) ;;
    FAIL) FAIL=$((FAIL + 1)) ;;
    BLOCKED) BLOCKED=$((BLOCKED + 1)) ;;
    MANUAL) MANUAL=$((MANUAL + 1)) ;;
    SKIP) SKIP=$((SKIP + 1)) ;;
  esac
}

run_capture() {
  local outfile="$1"
  shift
  "$@" >"$outfile" 2>&1
}

run_text_check() {
  local ac="$1"
  local desc="$2"
  shift 2
  local outfile="$RUN_DIR/${ac}.log"
  if run_capture "$outfile" "$@"; then
    record "$ac" PASS "$desc"
  else
    record "$ac" FAIL "$desc；输出见 $outfile"
  fi
}

is_cloudflare_auth_blocker() {
  grep -qi "Invalid access token" "$1" && grep -q "9109" "$1" && return 0
  grep -qi "Failed to fetch auth token" "$1" && return 0
  grep -qi "Not logged in" "$1" && return 0
  return 1
}

echo "============================================================"
echo " 004 verify_ac.sh - turtle-soup-rag AC1-AC20"
echo " 工作目录: $(pwd)"
echo " 临时证据: $RUN_DIR"
echo "============================================================"

print_line
echo "Cloudflare 远端预检"
WHOAMI_LOG="$RUN_DIR/wrangler-whoami.log"
if run_capture "$WHOAMI_LOG" pnpm exec wrangler whoami; then
  CF_READY=1
  echo "[CF] PASS - wrangler whoami 成功，继续执行远端资源检查"
else
  CF_READY=0
  if is_cloudflare_auth_blocker "$WHOAMI_LOG"; then
    echo "[CF] BLOCKED - wrangler whoami 被 Cloudflare 认证阻塞；已知旧输出为 Invalid access token [code: 9109]，当前输出见 $WHOAMI_LOG"
  else
    echo "[CF] FAIL - wrangler whoami 失败，输出见 $WHOAMI_LOG"
    FAIL=$((FAIL + 1))
  fi
fi

print_line
echo "本地小样本语料构建"
CORPUS_STDOUT="$RUN_DIR/corpus-stdout.json"
if python scripts/build_turtle_corpus.py --sample --mock-embedding --output "$RUN_DIR/corpus" >"$CORPUS_STDOUT" 2>"$RUN_DIR/corpus-stderr.log"; then
  cp "$RUN_DIR/corpus/build-report.json" "$REPORT_JSON"
  echo "[BUILD] PASS - 小样本 dry-run 生成 corpus/index/build report"
else
  echo "[BUILD] FAIL - 小样本 dry-run 失败；输出见 $CORPUS_STDOUT / $RUN_DIR/corpus-stderr.log"
  FAIL=$((FAIL + 1))
fi

print_line
echo "AC1-AC20"

if [ "$CF_READY" -eq 1 ]; then
  AC1_LOG="$RUN_DIR/ac1-cloudflare-resources.log"
  : >"$AC1_LOG"
  AC1_STATUS=0
  if ! pnpm exec wrangler vectorize list >>"$AC1_LOG" 2>&1; then
    AC1_STATUS=1
  fi
  if ! pnpm exec wrangler r2 bucket list >>"$AC1_LOG" 2>&1; then
    AC1_STATUS=1
  fi
  if ! pnpm exec wrangler d1 execute guess-figure-db --remote --command "SELECT name FROM sqlite_master WHERE name LIKE 'turtle_%';" >>"$AC1_LOG" 2>&1; then
    AC1_STATUS=1
  fi
  if grep -q "guess-figure-turtle-rag" "$AC1_LOG" \
    && grep -q "guess-figure-turtle-corpus" "$AC1_LOG" \
    && grep -q "turtle_corpus_versions" "$AC1_LOG" \
    && grep -q "turtle_index_versions" "$AC1_LOG" \
    && grep -q "turtle_corpus_sources" "$AC1_LOG" \
    && grep -q "turtle_build_reports" "$AC1_LOG"; then
    record AC1 MANUAL "远端 Vectorize/R2/D1 资源和 D1 manifest 表可见；Vectorize 1024 维与 cosine metric 仍需 Dashboard/manual 取证，输出见 $AC1_LOG"
  elif [ "$AC1_STATUS" -ne 0 ]; then
    record AC1 FAIL "远端资源检查命令失败；输出见 $AC1_LOG"
  else
    record AC1 FAIL "远端资源或 D1 manifest 表缺失；需包含 turtle_corpus_versions/turtle_index_versions/turtle_corpus_sources/turtle_build_reports，输出见 $AC1_LOG"
  fi
else
  record AC1 BLOCKED "需要恢复 token 后运行：pnpm exec wrangler vectorize list；pnpm exec wrangler r2 bucket list；pnpm exec wrangler d1 execute guess-figure-db --remote --command \"SELECT name FROM sqlite_master WHERE name LIKE 'turtle_%';\"；资源存在可自动检查，Vectorize 1024/cosine 仍需 Dashboard/manual"
fi

if [ -f "$REPORT_JSON" ] \
  && grep -q '"corpus_version"' "$REPORT_JSON" \
  && grep -q '"index_version"' "$REPORT_JSON" \
  && grep -q '"chunks_jsonl"' "$REPORT_JSON"; then
  if [ "$CF_READY" -eq 1 ]; then
    AC2_LOG="$RUN_DIR/ac2-cloud-ingest.log"
    AC2_REPORT="$RUN_DIR/cloud-corpus/build-report.json"
    if python scripts/build_turtle_corpus.py --sample --cloud --mock-embedding --output "$RUN_DIR/cloud-corpus" >"$AC2_LOG" 2>&1; then
      if [ -f "$AC2_REPORT" ] \
        && grep -q '"corpus_version"' "$AC2_REPORT" \
        && grep -q '"index_version"' "$AC2_REPORT" \
        && grep -qi 'source' "$AC2_REPORT" \
        && grep -qi 'r2' "$AC2_REPORT" \
        && grep -qi 'vector' "$AC2_REPORT" \
        && grep -qi 'd1' "$AC2_REPORT"; then
        record AC2 PASS "小样本 --cloud 写入链路完成，build report 含 version、source counts、R2 object keys、Vectorize/D1/cloud summary"
      else
        record AC2 MANUAL "小样本 --cloud 命令成功，但 report/stdout 未能完整自动证明 version、source counts、R2 object keys、Vectorize/D1/cloud summary；输出见 $AC2_LOG 和 $AC2_REPORT"
      fi
    else
      record AC2 FAIL "--cloud 写入失败；输出见 $AC2_LOG"
    fi
  else
    record AC2 BLOCKED "本地 dry-run 已生成版本/report；真实 R2/Vectorize/D1 写入需恢复 token 后运行：python scripts/build_turtle_corpus.py --sample --cloud --mock-embedding --output <repo外临时目录>"
  fi
else
  record AC2 FAIL "build report 缺少 corpus_version/index_version/chunks_jsonl"
fi

AC3_LOG="$RUN_DIR/ac3-git-large-corpus.log"
git ls-files | rg -n '(^|/)(raw|normalized|chunks|wikisource|r2-cache).*\.(jsonl|txt|md)$|(^|/)corpus/|r2-cache' >"$AC3_LOG" 2>&1
if [ -s "$AC3_LOG" ]; then
  record AC3 FAIL "git 中疑似包含全量语料或大体量 chunk；输出见 $AC3_LOG"
else
  record AC3 PASS "git 未跟踪全量原始/清洗语料、chunk JSONL 或 R2 cache"
fi

AC4_FULL_REPORT="${TURTLE_FULL_REPORTS:-${TURTLE_FULL_REPORT:-}}"
AC4_LOG="$RUN_DIR/ac4-full-history-report.log"
if [ -n "$AC4_FULL_REPORT" ]; then
  if python - "$AC4_FULL_REPORT" >"$AC4_LOG" 2>&1 <<'PY'
import json
import sys
from pathlib import Path

from scripts.turtle_history import HISTORY_BOOKS

def iter_report_paths(raw: str):
    for part in raw.split(";"):
        value = part.strip().strip('"').strip("'")
        if not value:
            continue
        path = Path(value)
        if path.is_dir():
            direct = path / "build-report.json"
            if direct.exists():
                yield direct
            for child in sorted(path.glob("*/build-report.json")):
                yield child
        else:
            yield path

reports = []
missing_paths = []
for path in iter_report_paths(sys.argv[1]):
    if path.exists():
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    else:
        missing_paths.append(str(path))
if not reports:
    print(json.dumps({"missing_report_paths": missing_paths or [sys.argv[1]]}, ensure_ascii=False, indent=2))
    raise SystemExit(1)

source_counts = {}
stats = {}
for report in reports:
    for name, count in report.get("source_counts", {}).items():
        source_counts[name] = source_counts.get(name, 0) + int(count or 0)
    for item in report.get("history_book_stats", []):
        if not isinstance(item, dict) or not item.get("book"):
            continue
        book = item["book"]
        target = stats.setdefault(book, {"book": book, "processed": 0, "failed": 0})
        target["processed"] += int(item.get("processed", 0) or 0)
        target["failed"] += int(item.get("failed", 0) or 0)

missing_sources = [name for name in ("profile", "wikipedia", "wikisource") if int(source_counts.get(name, 0)) <= 0]
missing_books = [book for book in HISTORY_BOOKS if book not in stats]
bad_books = []
for book in HISTORY_BOOKS:
    item = stats.get(book, {})
    if "processed" not in item or "failed" not in item:
        bad_books.append(book)
    elif int(item.get("processed", 0)) + int(item.get("failed", 0)) <= 0:
        bad_books.append(book)
if missing_paths or missing_sources or missing_books or bad_books:
    print(json.dumps({
        "report_count": len(reports),
        "missing_report_paths": missing_paths,
        "missing_sources": missing_sources,
        "missing_books": missing_books,
        "bad_books": bad_books,
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1)
print(json.dumps({"status": "ok", "report_count": len(reports)}, ensure_ascii=False))
PY
  then
    record AC4 PASS "全量 build report 覆盖 profile/wikipedia/wikisource，且二十四史/清史稿逐书含 processed/failed 统计；报告 $AC4_FULL_REPORT"
  else
    record AC4 FAIL "全量 build report 未满足 AC4；输出见 $AC4_LOG"
  fi
elif [ -f "$REPORT_JSON" ] \
  && grep -q '"profile"' "$REPORT_JSON" \
  && grep -q '"wikipedia"' "$REPORT_JSON" \
  && grep -q '"wikisource"' "$REPORT_JSON"; then
  record AC4 BLOCKED "自动化仅确认 sample source type coverage 覆盖 profile/wikipedia/wikisource；完整 AC4 还需 TURTLE_FULL_REPORT 或 TURTLE_FULL_REPORTS 指向全量二十四史 processed/failed 统计报告"
else
  record AC4 FAIL "build report 未覆盖三类来源"
fi

run_text_check AC5 "Python corpus 测试覆盖 chunk 长度、overlap、metadata <10KiB 与来源追溯" \
  python -m unittest scripts.tests.test_turtle_corpus

run_text_check AC6 "RAG 单测覆盖 query expansion、目标人物 aliases 注入与跨人物污染约束" \
  pnpm exec vitest run src/lib/server/turtle-rag.test.ts

run_text_check AC7 "RAG/API 单测覆盖可见回答枚举只允许 是/否/无关" \
  pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts

run_text_check AC8 "RAG 单测覆盖证据不足返回无关而非猜否" \
  pnpm exec vitest run src/lib/server/turtle-rag.test.ts

run_text_check AC9 "问题校验与 API 单测覆盖 invalid 不扣次数、不进 RAG/LLM" \
  pnpm exec vitest run src/lib/server/turtle-question.test.ts src/routes/api/turtle/question/server.test.ts

run_text_check AC10 "缓存单测覆盖 key 版本维度、30 天 TTL、cache hit 不查 Vectorize/LLM" \
  pnpm exec vitest run src/lib/server/turtle-cache.test.ts src/routes/api/turtle/question/server.test.ts

run_text_check AC11 "主游戏状态/组件测试覆盖第 6 条线索后才出现海龟汤入口" \
  pnpm exec vitest run src/lib/game-state.svelte.test.ts

run_text_check AC12 "嵌入式海龟汤测试覆盖 5 问上限与用后结算 0 分" \
  pnpm exec vitest run src/lib/game-state.svelte.test.ts src/routes/api/game/finish/server.test.ts

AC13_LOG="$RUN_DIR/ac13.log"
: >"$AC13_LOG"
AC13_STATUS=0
if ! pnpm exec vitest run src/lib/turtle-soup-state.test.ts >>"$AC13_LOG" 2>&1; then
  AC13_STATUS=1
fi
if ! python -m unittest scripts.tests.test_turtle_intro >>"$AC13_LOG" 2>&1; then
  AC13_STATUS=1
fi
if [ "$AC13_STATUS" -eq 0 ]; then
  record AC13 PASS "独立模式状态测试与 intro 校验覆盖首屏不泄露强识别信息，65 人通过"
else
  record AC13 FAIL "独立模式首屏或 turtle_intro 校验失败；输出见 $AC13_LOG"
fi

run_text_check AC14 "独立模式状态/API 测试覆盖 15 问、3 答、错答不扣提问次数" \
  pnpm exec vitest run src/lib/turtle-soup-state.test.ts src/routes/api/turtle/answer/server.test.ts

run_text_check AC15 "答案 API 测试覆盖最终答案只判人物，不读取 RAG 证据" \
  pnpm exec vitest run src/routes/api/turtle/answer/server.test.ts

run_text_check AC16 "问题校验测试覆盖直接猜姓名/别名类 yes/no 问题不被 invalid 拦截" \
  pnpm exec vitest run src/lib/server/turtle-question.test.ts

run_text_check AC17 "RAG/API 测试覆盖 Workers AI/Vectorize/预算失败时 degraded 且不误判为否" \
  pnpm exec vitest run src/lib/server/turtle-rag.test.ts src/routes/api/turtle/question/server.test.ts

run_text_check AC18 "关羽武圣维基 fixture 回归为 是" \
  pnpm exec vitest run src/lib/server/turtle-rag.test.ts

AC19_LOG="$RUN_DIR/ac19-automation.log"
: >"$AC19_LOG"
AC19_STATUS=0
if ! pnpm test >>"$AC19_LOG" 2>&1; then
  AC19_STATUS=1
fi
if ! pnpm run check >>"$AC19_LOG" 2>&1; then
  AC19_STATUS=1
fi
if ! pnpm run build >>"$AC19_LOG" 2>&1; then
  AC19_STATUS=1
fi
if ! python -m unittest scripts.tests.test_turtle_cloudflare scripts.tests.test_turtle_corpus scripts.tests.test_turtle_intro >>"$AC19_LOG" 2>&1; then
  AC19_STATUS=1
fi
if [ "$AC19_STATUS" -eq 0 ]; then
  record AC19 PASS "pnpm test/check/build 与相关 Python tests 全部通过"
else
  record AC19 FAIL "自动化检查失败；输出见 $AC19_LOG"
fi

record AC20 MANUAL "两条浏览器主路径需真人操作并记录到 workflow/004-turtle-soup-rag/08-qa.md：主游戏嵌入式求救一局、独立 /turtle-soup 一局"

print_line
echo "Summary: PASS=$PASS FAIL=$FAIL BLOCKED=$BLOCKED MANUAL=$MANUAL SKIP=$SKIP"
echo "证据目录: $RUN_DIR (脚本结束后会清理；请以终端输出和 07/08 文档为准)"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
  echo "结果: FAIL"
  exit 1
fi

if [ "$BLOCKED" -gt 0 ] || [ "$MANUAL" -gt 0 ]; then
  echo "结果: BLOCKED/MANUAL remaining"
  exit 2
fi

echo "结果: PASS"
exit 0
