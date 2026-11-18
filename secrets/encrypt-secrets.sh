#!/bin/sh
# Encrypt secrets/secrets.yaml to secrets/secrets.sops.yaml, then remove the
# plaintext so none stays at rest. A plain `sops encrypt in > out` truncates out
# before sops runs, so check the input, encrypt to a temp file, then move.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

if [ ! -s secrets/secrets.yaml ]; then
  echo "secrets/secrets.yaml is missing or empty; run task sops:decrypt first." >&2
  exit 1
fi

umask 077
tmp="secrets/.secrets.sops.yaml.tmp"
trap 'rm -f "$tmp"' EXIT HUP INT TERM

docker compose -f compose.example.yaml run --rm -T --user "$(id -u):$(id -g)" \
  sops --config secrets/.sops.yaml encrypt secrets/secrets.yaml > "$tmp"
mv "$tmp" secrets/secrets.sops.yaml
chmod 644 secrets/secrets.sops.yaml
rm -f secrets/secrets.yaml
echo "Encrypted to secrets/secrets.sops.yaml. Removed plaintext secrets/secrets.yaml, so none stays at rest."
