#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def default_config_path() -> str:
    return os.environ.get("TAKOPI_MATRIX_NOTIFY_CONFIG", "takopi.toml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send VPS worker status to the project's Matrix room.")
    parser.add_argument("--event", choices=("start", "progress", "finish", "error"), required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--tmp-dir", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--config", default=default_config_path())
    parser.add_argument("--message", default="")
    parser.add_argument("--worker-exit-code", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_cfg(path: Path) -> tuple[str, str, str]:
    cfg = tomllib.loads(path.read_text())
    matrix = cfg["transports"]["matrix"]
    room_projects = matrix.get("room_projects", {})
    project = args.project
    room_id = None
    for candidate_room_id, mapped_project in room_projects.items():
        if mapped_project == project:
            room_id = candidate_room_id
            break
    if room_id is None:
        raise KeyError(f"No Matrix room mapped for project {project}")
    return str(matrix["homeserver"]).rstrip("/"), str(matrix["access_token"]), str(room_id)


def send_message(homeserver: str, access_token: str, room_id: str, body: str) -> None:
    txn = f"cbs-worker-{int(time.time())}-{hashlib.sha1(body.encode()).hexdigest()[:12]}"
    encoded_room = urllib.parse.quote(room_id, safe="")
    url = f"{homeserver}/_matrix/client/v3/rooms/{encoded_room}/send/m.room.message/{txn}"
    payload = {"msgtype": "m.text", "body": body}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    urllib.request.urlopen(request, timeout=30).read()


def tmp_activity(tmp_dir: Path) -> tuple[int, int]:
    files = [path for path in tmp_dir.rglob("*") if path.is_file()]
    if not files:
        return 0, 0
    return len(files), sum(path.stat().st_size for path in files)


def db_summary(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {
            "ok_count": 0,
            "title_rows": 0,
            "in_progress": "",
            "latest_ok": "",
        }
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ok_count = conn.execute("select count(*) from archives where status = 'ok'").fetchone()[0]
        title_rows = conn.execute("select count(*) from titles").fetchone()[0]
        in_progress_row = conn.execute(
            "select archive_name from archives where status = 'in_progress' order by archive_name desc limit 1"
        ).fetchone()
        latest_ok_row = conn.execute(
            "select archive_name from archives where status = 'ok' order by finished_at desc limit 1"
        ).fetchone()
        return {
            "ok_count": int(ok_count),
            "title_rows": int(title_rows),
            "in_progress": str(in_progress_row["archive_name"]) if in_progress_row else "",
            "latest_ok": str(latest_ok_row["archive_name"]) if latest_ok_row else "",
        }
    finally:
        conn.close()


def progress_message(summary: dict[str, object], tmp_dir: Path) -> str:
    tmp_file_count, tmp_total_bytes = tmp_activity(tmp_dir)
    return (
        f"cbs worker progress\n"
        f"ok archives: {summary['ok_count']}\n"
        f"title rows: {summary['title_rows']}\n"
        f"in progress: {summary['in_progress'] or 'none'}\n"
        f"latest ok: {summary['latest_ok'] or 'none'}\n"
        f"tmp files: {tmp_file_count}\n"
        f"tmp bytes: {tmp_total_bytes}"
    )


def maybe_send_progress(
    homeserver: str,
    access_token: str,
    room_id: str,
    state_file: Path,
    body: str,
    force: bool,
) -> None:
    digest = hashlib.sha1(body.encode()).hexdigest()
    if state_file.exists() and not force:
        previous = json.loads(state_file.read_text())
        if previous.get("digest") == digest:
            return
    send_message(homeserver, access_token, room_id, body)
    state_file.write_text(json.dumps({"digest": digest}, sort_keys=True))


args = parse_args()

try:
    homeserver, access_token, room_id = load_cfg(Path(args.config))
except Exception as exc:  # pragma: no cover - operational fallback
    print(f"matrix notify disabled: {exc}", file=sys.stderr)
    raise SystemExit(0)

db_path = Path(args.db)
tmp_dir = Path(args.tmp_dir)
state_file = Path(args.state_file)
state_file.parent.mkdir(parents=True, exist_ok=True)

try:
    if args.event == "start":
        body = f"cbs worker started\nproject: {args.project}"
        send_message(homeserver, access_token, room_id, body)
        state_file.write_text(json.dumps({"digest": ""}))
    elif args.event == "progress":
        body = progress_message(db_summary(db_path), tmp_dir)
        maybe_send_progress(homeserver, access_token, room_id, state_file, body, args.force)
    elif args.event == "finish":
        summary = db_summary(db_path)
        body = (
            f"cbs worker finished\n"
            f"ok archives: {summary['ok_count']}\n"
            f"title rows: {summary['title_rows']}\n"
            f"latest ok: {summary['latest_ok'] or 'none'}"
        )
        send_message(homeserver, access_token, room_id, body)
    else:
        summary = db_summary(db_path)
        body = (
            f"cbs worker error\n"
            f"exit code: {args.worker_exit_code}\n"
            f"message: {args.message}\n"
            f"ok archives: {summary['ok_count']}\n"
            f"title rows: {summary['title_rows']}\n"
            f"in progress: {summary['in_progress'] or 'none'}"
        )
        send_message(homeserver, access_token, room_id, body)
except urllib.error.URLError as exc:  # pragma: no cover - operational fallback
    print(f"matrix notify failed: {exc}", file=sys.stderr)
    raise SystemExit(0)
