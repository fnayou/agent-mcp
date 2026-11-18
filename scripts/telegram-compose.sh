#!/bin/sh
# Run `scripts/compose.sh <args>` with TELEGRAM_API_ID and
# TELEGRAM_API_HASH decrypted from secrets/secrets.sops.yaml into a mode-600
# temporary file outside the repository. Only those two values are extracted.
# The file is deleted on exit, success or failure. Values are never printed.
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

extract() {
  sh scripts/compose.sh run --rm -T --user "$(id -u):$(id -g)" \
    sops --config secrets/.sops.yaml decrypt --extract "[\"$1\"]" secrets/secrets.sops.yaml
}

for name in TELEGRAM_API_ID TELEGRAM_API_HASH; do
  value="$(extract "$name")"
  printf '%s=%s\n' "$name" "$value" >> "$env_file"
done
chmod 600 "$env_file"

if grep -q REPLACE_ME "$env_file"; then
  echo "secrets/secrets.sops.yaml still holds placeholders; set real values with task sops:decrypt, edit, task sops:encrypt" >&2
  exit 1
fi

TELEGRAM_ENV_FILE="$env_file" sh scripts/compose.sh "$@"
