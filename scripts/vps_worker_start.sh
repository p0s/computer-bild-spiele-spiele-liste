#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

ITEM="${ITEM:-cbs-2000-09}"
MODE="${MODE:-titles}"
TITLE_STRATEGY="${TITLE_STRATEGY:-auto}"
ISSUE_SEARCH_LIMIT="${ISSUE_SEARCH_LIMIT:-5}"
BENCHMARK_SAMPLE="${BENCHMARK_SAMPLE:-6}"
BENCHMARK_SEED="${BENCHMARK_SEED:-1}"
USE_ARCHIVE_OCR="${USE_ARCHIVE_OCR:-1}"
USE_REDUMP="${USE_REDUMP:-0}"
RESUME="${RESUME:-1}"
LIMIT="${LIMIT:-}"
SYNC_FIRST="${SYNC_FIRST:-1}"

if [[ "$SYNC_FIRST" == "1" ]]; then
  "$SCRIPT_DIR/vps_worker_sync.sh"
fi

run_env=(
  "ITEM=$ITEM"
  "MODE=$MODE"
  "TITLE_STRATEGY=$TITLE_STRATEGY"
  "OUT_DIR=$REMOTE_RESULTS_DIR"
  "TMP_DIR=$REMOTE_TMP_WORK_DIR"
  "ISSUE_SEARCH_LIMIT=$ISSUE_SEARCH_LIMIT"
  "BENCHMARK_SAMPLE=$BENCHMARK_SAMPLE"
  "BENCHMARK_SEED=$BENCHMARK_SEED"
  "USE_ARCHIVE_OCR=$USE_ARCHIVE_OCR"
  "USE_REDUMP=$USE_REDUMP"
  "RESUME=$RESUME"
  "LIMIT=$LIMIT"
)

printf -v env_prefix '%q ' "${run_env[@]}"
worker_cmd="set -euo pipefail; cd \"$REMOTE_REPO_DIR\"; mkdir -p \"$REMOTE_RESULTS_DIR\"; ${env_prefix}bash scripts/vps_worker_run.sh >> \"$REMOTE_LOG_PATH\" 2>&1"

agentbox_exec "set -euo pipefail
if tmux has-session -t \"$SESSION_NAME\" 2>/dev/null; then
  echo session_exists=$SESSION_NAME
  exit 0
fi
tmux new-session -d -s \"$SESSION_NAME\" $(printf '%q' "$worker_cmd")
echo session_started=$SESSION_NAME
echo log=$REMOTE_LOG_PATH
echo db=$REMOTE_DB_PATH"
