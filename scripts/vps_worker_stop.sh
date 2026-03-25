#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

agentbox_exec "if tmux has-session -t \"$SESSION_NAME\" 2>/dev/null; then tmux kill-session -t \"$SESSION_NAME\"; echo session_stopped=$SESSION_NAME; else echo session_missing=$SESSION_NAME; fi"
