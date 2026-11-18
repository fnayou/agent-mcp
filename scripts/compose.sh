#!/bin/sh
# Every Compose call goes through here: `docker compose` on the tracked
# compose.example.yaml, plus the ignored compose.override.yaml when it exists
# (machine-specific settings). Run from any directory.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

if [ -f compose.override.yaml ]; then
  exec docker compose -f compose.example.yaml -f compose.override.yaml "$@"
fi
exec docker compose -f compose.example.yaml "$@"
