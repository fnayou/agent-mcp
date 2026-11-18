#!/bin/sh
# Run `docker compose -f compose.example.yaml <args>` with TELEGRAM_API_ID and
# TELEGRAM_API_HASH decrypted from secrets.sops.yaml into a mode-600 temporary
# file outside the repository. The file is deleted on exit, success or failure.
# Values are never printed.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

umask 077
env_file="$(mktemp "${TMPDIR:-/tmp}/agent-mcp-telegram.XXXXXX")"
trap 'rm -f "$env_file"' EXIT HUP INT TERM

env_dir="$(cd "$(dirname "$env_file")" && pwd -P)"
case "$env_dir/" in
  "$root"/*) echo "refusing to write decrypted secrets inside the repository: $env_file" >&2; exit 1 ;;
esac

docker compose -f compose.example.yaml run --rm -T --user "$(id -u):$(id -g)" \
  sops decrypt --output-type dotenv secrets.sops.yaml > "$env_file"
chmod 600 "$env_file"

if grep -q REPLACE_ME "$env_file"; then
  echo "secrets.sops.yaml still holds placeholders; set real values with task secrets:edit" >&2
  exit 1
fi

TELEGRAM_ENV_FILE="$env_file" docker compose -f compose.example.yaml "$@"
