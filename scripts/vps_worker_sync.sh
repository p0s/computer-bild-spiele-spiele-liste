#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

REMOTE_ORIGIN="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)"
BUNDLE_PATH="$(mktemp "${TMPDIR:-/tmp}/${REPO_NAME}.XXXXXX.bundle")"
REMOTE_BUNDLE_PATH="$REMOTE_TMP_DIR/${REPO_NAME}.bundle"

cleanup() {
  rm -f "$BUNDLE_PATH"
}
trap cleanup EXIT

git -C "$REPO_ROOT" bundle create "$BUNDLE_PATH" --all

cat "$BUNDLE_PATH" | ssh "$VPS_HOST" "set -euo pipefail; C=\$(docker ps --format '{{.Names}}' | grep '^agentbox-' | head -n1); docker exec -i -u agent \"\$C\" bash -lc 'cat > \"$REMOTE_BUNDLE_PATH\"'"

agentbox_exec "set -euo pipefail
REPO=\"$REMOTE_REPO_DIR\"
BUNDLE=\"$REMOTE_BUNDLE_PATH\"
mkdir -p \"\$(dirname \"$REPO\")\"
if [ -d \"$REPO/.git\" ]; then
  git -C \"$REPO\" fetch \"$BUNDLE\" master
  git -C \"$REPO\" checkout master
  git -C \"$REPO\" reset --hard FETCH_HEAD
else
  rm -rf \"$REPO\"
  git clone \"$BUNDLE\" \"$REPO\"
  git -C \"$REPO\" checkout master
fi
if [ -n \"$REMOTE_ORIGIN\" ]; then
  git -C \"$REPO\" remote remove origin >/dev/null 2>&1 || true
  git -C \"$REPO\" remote add origin \"$REMOTE_ORIGIN\"
fi
mkdir -p \"$REMOTE_RESULTS_DIR\"
rm -f \"$BUNDLE\"
echo repo=$REPO
echo head=\$(git -C \"$REPO\" rev-parse --short HEAD)
echo branch=\$(git -C \"$REPO\" rev-parse --abbrev-ref HEAD)
echo origin=\$(git -C \"$REPO\" remote get-url origin || true)"
