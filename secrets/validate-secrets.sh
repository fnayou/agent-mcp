#!/bin/sh
# Fail if any secrets/*.sops.yaml is not SOPS-encrypted, or if a plaintext
# secrets file is left behind. Runs on the host without a key, and in CI.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

err=0

# Every *.sops.yaml carries SOPS metadata and encrypted (ENC[...]) values.
for f in secrets/*.sops.yaml secrets/*.sops.yml; do
  [ -f "$f" ] || continue
  if ! grep -q '^sops:' "$f" || ! grep -q 'ENC\[' "$f"; then
    echo "ERROR: $f is not SOPS-encrypted (missing 'sops:' metadata or ENC[...] values)" >&2
    err=1
  fi
done

# No plaintext secrets file may stay at rest; only the .example template.
for f in secrets/secrets.yaml secrets/secrets.yml; do
  if [ -f "$f" ]; then
    echo "ERROR: plaintext $f present; run task sops:encrypt, which removes it" >&2
    err=1
  fi
done

if [ "$err" -eq 0 ]; then
  echo "OK: secrets are encrypted; no plaintext at rest"
fi
exit "$err"
