#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CHECK_TMP="$(mktemp -d "${TMPDIR:-/tmp}/cbs-check.XXXXXX")"

cleanup() {
  rm -rf "$CHECK_TMP"
}
trap cleanup EXIT

cd "$REPO_ROOT"
ruff check .
ruff format --check .
"$PYTHON_BIN" -m build --outdir "$CHECK_TMP/dist"
"$PYTHON_BIN" -m compileall -q scripts tests
"$PYTHON_BIN" -m unittest discover -s tests
bash -n scripts/vps_worker_common.sh scripts/vps_worker_fetch_results.sh scripts/vps_worker_run.sh \
  scripts/vps_worker_start.sh scripts/vps_worker_status.sh scripts/vps_worker_stop.sh \
  scripts/vps_worker_sync.sh scripts/vps_worker_tail.sh
"$PYTHON_BIN" scripts/release_contract.py check
"$PYTHON_BIN" scripts/media_release_contract.py
"$PYTHON_BIN" scripts/release_audit.py \
  --skip-git-fetch \
  --report-path "$CHECK_TMP/release-audit.md" \
  --sample-path "$CHECK_TMP/release-sample.csv"
