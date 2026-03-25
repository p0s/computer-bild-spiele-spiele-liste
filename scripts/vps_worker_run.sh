#!/usr/bin/env bash
set -euo pipefail

ITEM="${ITEM:-cbs-2000-09}"
MODE="${MODE:-titles}"
TITLE_STRATEGY="${TITLE_STRATEGY:-auto}"
OUT_DIR="${OUT_DIR:-results}"
TMP_DIR="${TMP_DIR:-/tmp/cbs-worker}"
PROJECT_NAME="${PROJECT_NAME:-computer-bild-spiele-spiele-liste}"
ISSUE_SEARCH_LIMIT="${ISSUE_SEARCH_LIMIT:-5}"
BENCHMARK_SAMPLE="${BENCHMARK_SAMPLE:-6}"
BENCHMARK_SEED="${BENCHMARK_SEED:-1}"
USE_ARCHIVE_OCR="${USE_ARCHIVE_OCR:-1}"
USE_REDUMP="${USE_REDUMP:-0}"
RESUME="${RESUME:-1}"
LIMIT="${LIMIT:-}"
STATUS_INTERVAL_SECONDS="${STATUS_INTERVAL_SECONDS:-300}"
STATUS_STATE_FILE="${STATUS_STATE_FILE:-$OUT_DIR/.vps_worker_status.json}"
MATRIX_NOTIFY_CONFIG="${MATRIX_NOTIFY_CONFIG:-takopi.toml}"

args=(
  python3
  scripts/index_cbs_exes.py
  --item "$ITEM"
  --mode "$MODE"
  --title-strategy "$TITLE_STRATEGY"
  --out-dir "$OUT_DIR"
  --tmp-dir "$TMP_DIR"
  --issue-search-limit "$ISSUE_SEARCH_LIMIT"
  --benchmark-sample "$BENCHMARK_SAMPLE"
  --benchmark-seed "$BENCHMARK_SEED"
)

if [[ "$USE_ARCHIVE_OCR" == "1" ]]; then
  args+=(--use-archive-ocr)
fi

if [[ "$USE_REDUMP" == "1" ]]; then
  args+=(--use-redump)
fi

if [[ "$RESUME" == "1" ]]; then
  args+=(--resume)
fi

if [[ -n "$LIMIT" ]]; then
  args+=(--limit "$LIMIT")
fi

notify() {
  python3 scripts/vps_worker_matrix_notify.py \
    --event "$1" \
    --project "$PROJECT_NAME" \
    --db "$OUT_DIR/cbs_titles.sqlite" \
    --tmp-dir "$TMP_DIR" \
    --state-file "$STATUS_STATE_FILE" \
    --config "$MATRIX_NOTIFY_CONFIG" \
    ${2:+--message "$2"} \
    ${3:+--worker-exit-code "$3"} || true
}

mkdir -p "$OUT_DIR" "$TMP_DIR"

notify start

"${args[@]}" &
worker_pid=$!

cleanup() {
  if kill -0 "$worker_pid" 2>/dev/null; then
    kill "$worker_pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM

while kill -0 "$worker_pid" 2>/dev/null; do
  sleep "$STATUS_INTERVAL_SECONDS"
  if kill -0 "$worker_pid" 2>/dev/null; then
    notify progress
  fi
done

wait "$worker_pid"
worker_rc=$?

if [[ "$worker_rc" -eq 0 ]]; then
  notify finish
else
  notify error "worker exited non-zero" "$worker_rc"
fi

exit "$worker_rc"
