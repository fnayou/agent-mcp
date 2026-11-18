#!/bin/sh
# Show ONE top-level value of secrets/secrets.sops.yaml through the sops tool
# container: `task sops:get -- [--copy] <NAME>`.
#
# It prints only when stdout is a terminal, so a secret cannot land in a pipe, a
# log or an assistant's transcript; `--copy` sends it to the clipboard instead.
# Every refusal happens before docker is called. There is no "all keys" mode:
# that is `task sops:decrypt`.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

store="secrets/secrets.sops.yaml"

usage() {
  echo "usage: task sops:get -- [--copy] <NAME>" >&2
  exit 2
}

copy=0
if [ "${1:-}" = "--copy" ]; then
  copy=1
  shift
fi
[ "$#" -eq 1 ] || usage
name="$1"

# A top-level key by exact name, never an --extract path: nothing the caller
# types reaches sops as syntax. `sops` is the file's metadata, not a secret.
case "$name" in
  ''|*[!A-Za-z0-9_]*|sops)
    echo "sops:get: '$name' is not a secret name (expected ^[A-Za-z0-9_]+\$)." >&2
    exit 2 ;;
esac

# Key names are plaintext in a SOPS file, so an unknown name is caught here
# without decrypting anything.
if ! grep -q "^$name:" "$store"; then
  echo "sops:get: no top-level '$name' in $store." >&2
  exit 1
fi

if [ "$copy" -eq 1 ]; then
  if ! command -v pbcopy >/dev/null 2>&1; then
    echo "sops:get: --copy needs pbcopy (macOS); run without --copy in a terminal." >&2
    exit 1
  fi
elif ! [ -t 1 ]; then
  echo "sops:get: stdout is not a terminal; refusing to print a secret." >&2
  echo "Run it in a terminal, or use --copy." >&2
  exit 1
fi

extract() {
  sh scripts/compose.sh run --rm -T --user "$(id -u):$(id -g)" \
    sops --config secrets/.sops.yaml decrypt --extract "[\"$name\"]" "$store"
}

if [ "$copy" -eq 1 ]; then
  # Captured, not piped: a failed decrypt must not leave a partial clipboard.
  # The command substitution drops the trailing newline.
  value="$(extract)"
  printf '%s' "$value" | pbcopy
  echo "sops:get: $name copied to the clipboard."
else
  extract
fi
