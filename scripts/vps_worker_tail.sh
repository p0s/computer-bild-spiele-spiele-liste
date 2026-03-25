#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

agentbox_exec "mkdir -p \"$REMOTE_RESULTS_DIR\" && touch \"$REMOTE_LOG_PATH\" && tail -n 200 -f \"$REMOTE_LOG_PATH\""
