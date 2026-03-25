#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

LOCAL_OUTPUT_DIR="${LOCAL_OUTPUT_DIR:-$REPO_ROOT/results/vps-linux-retry-$(date -u +%Y%m%d)}"
LOCAL_OUTPUT_DIR="$(cd "$(dirname "$LOCAL_OUTPUT_DIR")" && pwd)/$(basename "$LOCAL_OUTPUT_DIR")"
LOCAL_BASENAME="$(basename "$LOCAL_OUTPUT_DIR")"
LOCAL_PARENT="$(dirname "$LOCAL_OUTPUT_DIR")"
LOCAL_ARCHIVE_PATH="$LOCAL_PARENT/${LOCAL_BASENAME}.tar.gz"
LOCAL_TAR_SHA_PATH="$LOCAL_ARCHIVE_PATH.sha256"
LOCAL_FILE_SHA_PATH="$LOCAL_PARENT/${LOCAL_BASENAME}-files.sha256"
REMOTE_SOURCE_PATH="${REMOTE_SOURCE_PATH:-}"
SKIP_REMOTE_BASENAME="${SKIP_REMOTE_BASENAME:-vps-linux-full-20260324}"
REMOTE_TAR_PATH="$REMOTE_TMP_DIR/${LOCAL_BASENAME}.tar.gz"
REMOTE_TAR_SHA_PATH="$REMOTE_TAR_PATH.sha256"
REMOTE_FILE_SHA_PATH="$REMOTE_TMP_DIR/${LOCAL_BASENAME}-files.sha256"
REMOTE_SOURCE_BASENAME=""

mkdir -p "$LOCAL_PARENT"

if [[ -e "$LOCAL_OUTPUT_DIR" || -e "$LOCAL_ARCHIVE_PATH" ]]; then
  echo "local target already exists: $LOCAL_OUTPUT_DIR or $LOCAL_ARCHIVE_PATH" >&2
  exit 1
fi

discover_remote_source() {
  if [[ -n "$REMOTE_SOURCE_PATH" ]]; then
    printf '%s\n' "$REMOTE_SOURCE_PATH"
    return 0
  fi

  agentbox_exec "set -euo pipefail
export REMOTE_RESULTS_DIR='$REMOTE_RESULTS_DIR'
export REMOTE_TMP_DIR='$REMOTE_TMP_DIR'
export REMOTE_REPO_DIR='$REMOTE_REPO_DIR'
export SKIP_REMOTE_BASENAME='$SKIP_REMOTE_BASENAME'
python3 - <<'PY'
import os
from pathlib import Path

required = {'issue_titles.csv', 'master_games.csv', 'unresolved_issues.csv'}
roots = []
for value in (
    os.environ.get('REMOTE_RESULTS_DIR', ''),
    os.environ.get('REMOTE_REPO_DIR', '') + '/results' if os.environ.get('REMOTE_REPO_DIR') else '',
    os.environ.get('REMOTE_TMP_DIR', ''),
):
    if value:
        roots.append(Path(value))

skip = os.environ.get('SKIP_REMOTE_BASENAME', '')
candidates = []
for root in roots:
    if not root.exists():
        continue
    try:
        dirs = [root] + [path for path in root.rglob('*') if path.is_dir()]
    except OSError:
        continue
    for path in dirs:
        if path.name == skip:
            continue
        try:
            names = {child.name for child in path.iterdir() if child.is_file()}
        except OSError:
            continue
        if required.issubset(names):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            candidates.append((mtime, str(path)))

if not candidates:
    raise SystemExit('could not find a retry snapshot directory on the VPS')

candidates.sort(reverse=True)
print(candidates[0][1])
PY"
}

REMOTE_SOURCE_PATH="$(discover_remote_source)"
REMOTE_SOURCE_BASENAME="$(basename "$REMOTE_SOURCE_PATH")"
echo "remote_source=$REMOTE_SOURCE_PATH"

agentbox_exec "set -euo pipefail
SOURCE='$REMOTE_SOURCE_PATH'
REMOTE_TAR='$REMOTE_TAR_PATH'
REMOTE_TAR_SHA='$REMOTE_TAR_SHA_PATH'
REMOTE_FILE_SHA='$REMOTE_FILE_SHA_PATH'
if [[ ! -d \"\$SOURCE\" ]]; then
  echo \"remote source is not a directory: \$SOURCE\" >&2
  exit 1
fi
for name in issue_titles.csv master_games.csv unresolved_issues.csv; do
  if [[ ! -f \"\$SOURCE/\$name\" ]]; then
    echo \"remote source missing \$name: \$SOURCE\" >&2
    exit 1
  fi
done
tar -C \"\$(dirname \"\$SOURCE\")\" -czf \"\$REMOTE_TAR\" \"\$(basename \"\$SOURCE\")\"
sha256sum \"\$REMOTE_TAR\" > \"\$REMOTE_TAR_SHA\"
(
  cd \"\$SOURCE\"
  : > \"\$REMOTE_FILE_SHA\"
  for name in .vps_worker_status.json all_title_candidates.csv cbs_titles.sqlite issue_titles.csv master_games.csv strategy_benchmark.csv titles_dedup.csv unresolved_issues.csv vps_supervisor.log; do
    if [[ -f \"\$name\" ]]; then
      sha256sum \"\$name\" >> \"\$REMOTE_FILE_SHA\"
    fi
  done
)
echo remote_tar=\$REMOTE_TAR
echo remote_tar_sha=\$REMOTE_TAR_SHA
echo remote_file_sha=\$REMOTE_FILE_SHA"

agentbox_exec "cat '$REMOTE_TAR_PATH'" > "$LOCAL_ARCHIVE_PATH"
agentbox_exec "cat '$REMOTE_TAR_SHA_PATH'" > "$LOCAL_TAR_SHA_PATH"
agentbox_exec "cat '$REMOTE_FILE_SHA_PATH'" > "$LOCAL_FILE_SHA_PATH"

mkdir -p "$LOCAL_OUTPUT_DIR"
tar -xzf "$LOCAL_ARCHIVE_PATH" -C "$LOCAL_PARENT"

if [[ "$REMOTE_SOURCE_BASENAME" != "$LOCAL_BASENAME" && -d "$LOCAL_PARENT/$REMOTE_SOURCE_BASENAME" && ! -e "$LOCAL_OUTPUT_DIR/.vps_worker_status.json" ]]; then
  rmdir "$LOCAL_OUTPUT_DIR" 2>/dev/null || true
  mv "$LOCAL_PARENT/$REMOTE_SOURCE_BASENAME" "$LOCAL_OUTPUT_DIR"
fi

if [[ ! -f "$LOCAL_OUTPUT_DIR/issue_titles.csv" || ! -f "$LOCAL_OUTPUT_DIR/master_games.csv" || ! -f "$LOCAL_OUTPUT_DIR/unresolved_issues.csv" ]]; then
  echo "fetched archive did not unpack the expected snapshot layout: $LOCAL_OUTPUT_DIR" >&2
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  local_tar_hash="$(shasum -a 256 "$LOCAL_ARCHIVE_PATH" | awk '{print $1}')"
  remote_tar_hash="$(awk '{print $1}' "$LOCAL_TAR_SHA_PATH")"
  if [[ "$local_tar_hash" != "$remote_tar_hash" ]]; then
    echo "tarball checksum mismatch after fetch" >&2
    exit 1
  fi
fi

echo "local_output_dir=$LOCAL_OUTPUT_DIR"
echo "local_archive=$LOCAL_ARCHIVE_PATH"
echo "local_tar_sha=$LOCAL_TAR_SHA_PATH"
echo "local_file_sha=$LOCAL_FILE_SHA_PATH"
