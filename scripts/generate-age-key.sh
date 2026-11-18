#!/bin/sh
# Create age/key.txt through the age-keygen tool container, never overwriting an
# existing key, then print the public key and check secrets/.sops.yaml.
# The private key is ignored by git and must never be committed.
set -eu

root="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$root"

key="age/key.txt"
config="secrets/.sops.yaml"

if [ -e "$key" ]; then
  echo "refusing to overwrite existing key: $key" >&2
  exit 1
fi

mkdir -p -m 700 age
docker compose -f compose.example.yaml run --rm -T --user "$(id -u):$(id -g)" age-keygen

public="$(grep '^# public key: ' "$key" | cut -d ' ' -f 4)"
if [ -z "$public" ]; then
  echo "could not read the public key from $key" >&2
  exit 1
fi
echo "Public key: $public"

if [ ! -f "$config" ]; then
  mkdir -p secrets
  cat > "$config" <<EOF
creation_rules:
  # Matches the plaintext input (secrets.yaml) and the encrypted output
  # (secrets.sops.yaml); excludes the committed secrets.yaml.example template.
  - path_regex: '(^|/)secrets(\.sops)?\.ya?ml\$'
    age:
      - $public
EOF
  echo "Created $config with this key."
elif grep -q "$public" "$config"; then
  echo "$config already lists this key."
else
  echo "ACTION REQUIRED: put $public in $config in place of the old key, then re-create secrets/secrets.sops.yaml." >&2
fi
echo "Back up $key now: git clean -fdx deletes it, and losing it makes the secrets unreadable."
