#!/usr/bin/env bash
set -euo pipefail

VPS_HOST="${VPS_HOST:?Set VPS_HOST to your SSH host alias}"
REPO_NAME="${REPO_NAME:-computer-bild-spiele-spiele-liste}"
SESSION_NAME="${SESSION_NAME:-cbs-worker}"
REMOTE_REPO_DIR="${REMOTE_REPO_DIR:-/workspace/repos/$REPO_NAME}"
REMOTE_TMP_DIR="${REMOTE_TMP_DIR:-/tmp}"
REMOTE_TMP_WORK_DIR="${REMOTE_TMP_WORK_DIR:-/tmp/cbs-worker}"
REMOTE_RESULTS_DIR="${REMOTE_RESULTS_DIR:-$REMOTE_REPO_DIR/results}"
REMOTE_LOG_PATH="${REMOTE_LOG_PATH:-$REMOTE_RESULTS_DIR/vps_worker.log}"
REMOTE_DB_PATH="${REMOTE_DB_PATH:-$REMOTE_RESULTS_DIR/cbs_titles.sqlite}"

agentbox_exec() {
  local inner="$1"
  printf '%s\n' "$inner" | ssh "$VPS_HOST" "set -euo pipefail; C=\$(docker ps --format '{{.Names}}' | grep '^agentbox-' | head -n1); docker exec -i -u agent \"\$C\" bash -s"
}
