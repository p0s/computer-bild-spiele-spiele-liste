#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/vps_worker_common.sh"

agentbox_exec "set -euo pipefail
echo session=$SESSION_NAME
if tmux has-session -t \"$SESSION_NAME\" 2>/dev/null; then
  echo session_status=running
else
  echo session_status=stopped
fi
echo repo=$REMOTE_REPO_DIR
if [ -f \"$REMOTE_DB_PATH\" ]; then
  python3 - <<'PY'
from pathlib import Path
import sqlite3
db = Path('$REMOTE_DB_PATH')
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
count = conn.execute('select count(*) from titles').fetchone()[0]
print(f'title_rows={count}')
row = conn.execute('select archive_name,status,started_at,finished_at from archives order by archive_name desc limit 5').fetchall()
for item in row:
    print(f\"archive\\t{item['archive_name']}\\t{item['status']}\\t{item['started_at'] or ''}\\t{item['finished_at'] or ''}\")
conn.close()
PY
else
  echo db_missing=$REMOTE_DB_PATH
fi
if [ -f \"$REMOTE_LOG_PATH\" ]; then
  echo 'log_tail_start'
  tail -n 20 \"$REMOTE_LOG_PATH\"
  echo 'log_tail_end'
fi
find \"$REMOTE_TMP_WORK_DIR\" -maxdepth 3 -type f -ls | sort | tail -n 10 || true"
