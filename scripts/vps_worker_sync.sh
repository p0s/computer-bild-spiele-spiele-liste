#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

BUNDLE_PATH="$(mktemp "${TMPDIR:-/tmp}/${REPO_NAME}.XXXXXX.bundle")"
REMOTE_BUNDLE_PATH="$REMOTE_TMP_DIR/${REPO_NAME}.bundle"

cleanup() {
  rm -f "$BUNDLE_PATH"
}
trap cleanup EXIT

git -C "$REPO_ROOT" bundle create "$BUNDLE_PATH" --all
agentbox_put_file "$BUNDLE_PATH" "$REMOTE_BUNDLE_PATH"

agentbox_exec "set -euo pipefail
REPO='$REMOTE_REPO_DIR'
BUNDLE='$REMOTE_BUNDLE_PATH'
EXPECTED='$REMOTE_REPO_ROOT/$REPO_NAME'
if [[ \"\$REPO\" != \"\$EXPECTED\" ]]; then
  echo \"refusing destructive sync outside exact repository target: \$REPO\" >&2
  exit 1
fi
mkdir -p \"\$(dirname \"\$REPO\")\"
if [[ -d \"\$REPO/.git\" ]]; then
  git -C \"\$REPO\" fetch \"\$BUNDLE\" master
  git -C \"\$REPO\" checkout master
  git -C \"\$REPO\" reset --hard FETCH_HEAD
else
  rm -rf \"\$REPO\"
  git clone \"\$BUNDLE\" \"\$REPO\"
  git -C \"\$REPO\" checkout master
fi
mkdir -p '$REMOTE_RESULTS_DIR'
rm -f \"\$BUNDLE\"
echo repo=\$REPO
echo head=\$(git -C \"\$REPO\" rev-parse --short HEAD)
echo branch=\$(git -C \"\$REPO\" rev-parse --abbrev-ref HEAD)
echo origin=\$(git -C \"\$REPO\" remote get-url origin || true)"
