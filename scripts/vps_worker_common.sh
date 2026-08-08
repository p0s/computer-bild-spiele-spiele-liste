#!/usr/bin/env bash
set -euo pipefail

VPS_HOST="${VPS_HOST:?Set VPS_HOST to your SSH host alias}"
REPO_NAME="${REPO_NAME:-computer-bild-spiele-spiele-liste}"
SESSION_NAME="${SESSION_NAME:-cbs-worker}"
REMOTE_REPO_ROOT="${REMOTE_REPO_ROOT:-/workspace/repos}"
REMOTE_REPO_DIR="${REMOTE_REPO_DIR:-$REMOTE_REPO_ROOT/$REPO_NAME}"
REMOTE_TMP_DIR="${REMOTE_TMP_DIR:-/tmp}"
REMOTE_TMP_WORK_DIR="${REMOTE_TMP_WORK_DIR:-/tmp/cbs-worker}"
REMOTE_RESULTS_DIR="${REMOTE_RESULTS_DIR:-$REMOTE_REPO_DIR/results}"
REMOTE_LOG_PATH="${REMOTE_LOG_PATH:-$REMOTE_RESULTS_DIR/vps_worker.log}"
REMOTE_DB_PATH="${REMOTE_DB_PATH:-$REMOTE_RESULTS_DIR/cbs_titles.sqlite}"
AGENTBOX_CONTAINER="${AGENTBOX_CONTAINER:-}"

validate_simple_name() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "unsafe $label: $value" >&2
    exit 1
  fi
}

validate_remote_path() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^/[A-Za-z0-9._/-]+$ || "$value" == *"//"* || "/$value/" == *"/../"* || "/$value/" == *"/./"* ]]; then
    echo "unsafe $label: $value" >&2
    exit 1
  fi
}

validate_simple_name "REPO_NAME" "$REPO_NAME"
validate_simple_name "SESSION_NAME" "$SESSION_NAME"
if [[ ! "$VPS_HOST" =~ ^[A-Za-z0-9._@:-]+$ ]]; then
  echo "unsafe VPS_HOST: $VPS_HOST" >&2
  exit 1
fi
if [[ -n "$AGENTBOX_CONTAINER" ]]; then
  validate_simple_name "AGENTBOX_CONTAINER" "$AGENTBOX_CONTAINER"
fi
validate_remote_path "REMOTE_REPO_ROOT" "$REMOTE_REPO_ROOT"
validate_remote_path "REMOTE_REPO_DIR" "$REMOTE_REPO_DIR"
validate_remote_path "REMOTE_TMP_DIR" "$REMOTE_TMP_DIR"
validate_remote_path "REMOTE_TMP_WORK_DIR" "$REMOTE_TMP_WORK_DIR"
validate_remote_path "REMOTE_RESULTS_DIR" "$REMOTE_RESULTS_DIR"
validate_remote_path "REMOTE_LOG_PATH" "$REMOTE_LOG_PATH"
validate_remote_path "REMOTE_DB_PATH" "$REMOTE_DB_PATH"
if [[ "$REMOTE_REPO_DIR" != "$REMOTE_REPO_ROOT/$REPO_NAME" ]]; then
  echo "REMOTE_REPO_DIR must be exactly $REMOTE_REPO_ROOT/$REPO_NAME" >&2
  exit 1
fi
if [[ "$REMOTE_RESULTS_DIR" != "$REMOTE_REPO_DIR/results" ]]; then
  echo "REMOTE_RESULTS_DIR must be exactly $REMOTE_REPO_DIR/results" >&2
  exit 1
fi
if [[ "$REMOTE_TMP_DIR" != "/tmp" || "$REMOTE_TMP_WORK_DIR" != "$REMOTE_TMP_DIR/"* ]]; then
  echo "remote temporary paths must stay below /tmp" >&2
  exit 1
fi

agentbox_remote_prefix() {
  cat <<EOF
set -euo pipefail
requested='$AGENTBOX_CONTAINER'
if [[ -n "\$requested" ]]; then
  if ! docker ps --format '{{.Names}}' | grep -Fqx -- "\$requested"; then
    echo "requested agentbox container is not running: \$requested" >&2
    exit 1
  fi
  container="\$requested"
else
  matches="\$(docker ps --format '{{.Names}}' | awk '/^agentbox-[A-Za-z0-9_.-]+\$/')"
  count="\$(printf '%s\n' "\$matches" | awk 'NF { count++ } END { print count + 0 }')"
  if [[ "\$count" -ne 1 ]]; then
    echo "expected exactly one running agentbox container, found \$count; set AGENTBOX_CONTAINER explicitly" >&2
    exit 1
  fi
  container="\$matches"
fi
EOF
}

agentbox_exec() {
  local inner="$1"
  local remote_command
  remote_command="$(agentbox_remote_prefix)"$'\n''docker exec -i -u agent "$container" bash -s'
  printf '%s\n' "$inner" | ssh "$VPS_HOST" "$remote_command"
}

agentbox_put_file() {
  local local_path="$1"
  local remote_path="$2"
  local remote_command
  validate_remote_path "agentbox destination" "$remote_path"
  remote_command="$(agentbox_remote_prefix)"$'\n'"docker exec -i -u agent \"\$container\" sh -c 'cat > \"\$1\"' sh '$remote_path'"
  ssh "$VPS_HOST" "$remote_command" < "$local_path"
}
