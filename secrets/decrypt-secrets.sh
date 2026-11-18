#!/bin/sh
# Decrypt secrets/secrets.sops.yaml to the plaintext secrets/secrets.yaml (ignored
# by git, mode 600). Writes a temp file then moves it, so a failed decrypt cannot
# destroy plaintext that is being edited.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

umask 077
tmp="secrets/.secrets.yaml.tmp"
trap 'rm -f "$tmp"' EXIT HUP INT TERM

docker compose -f compose.example.yaml run --rm -T --user "$(id -u):$(id -g)" \
  sops --config secrets/.sops.yaml decrypt secrets/secrets.sops.yaml > "$tmp"
mv "$tmp" secrets/secrets.yaml
echo "WARNING: plaintext at secrets/secrets.yaml. Do not commit it; task sops:encrypt removes it."
