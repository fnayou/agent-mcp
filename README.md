# fnayou/agent-mcp

Declare every MCP server once and install it into Claude Code, Codex, OpenCode and Pi on macOS, Arch and Debian.

## Getting started

Follow the [operator guide](docs/operator-guide.md): prerequisites, one-time setup per machine, install, day-to-day commands and undo.

## Server manifest

`servers.yaml` declares every MCP server and the dependencies it needs. `servers.schema.json` defines the format; `task manifest:check` validates the manifest, and `task doctor` runs the same check.

```yaml
schema_version: 1

requires:
  agent-browser:
    check:
      path: ${HOME}/.agents/skills/agent-browser/scripts/agent-browser-mcp
    hint: Install the agent-browser skill from https://github.com/fnayou/agent-skills

servers:
  playwright:
    description: Agent-only headless browser with an in-memory profile, for general web work
    transport: stdio
    command: ${HOME}/.agents/skills/agent-browser/scripts/agent-browser-mcp
    startup_timeout_sec: 30
    requires: [agent-browser]
    codex:
      tools:
        browser_navigate: { approval_mode: approve }
```

Server fields:

| Field | Meaning |
|---|---|
| `description` | Required. Shown by harnesses that support descriptions. |
| `transport` | Required. `stdio` or `http`. |
| `command`, `args` | `stdio` only; `command` is required. `${HOME}` is expanded at install time. |
| `env` | `stdio` only. Plain values; never secrets. |
| `url` | `http` only, required. |
| `service` | `http` only. Compose service that must be running. |
| `startup_timeout_sec` | Codex `startup_timeout_sec`; OpenCode `timeout.startup` in milliseconds. |
| `requires` | Names from the top-level `requires` map. Each entry has a `check` (`path` or `command`) and a `hint`. |
| `os` | `darwin`, `arch`, `debian`. Default: all. |
| `harnesses` | `claude`, `codex`, `opencode`, `pi`. Default: all. |
| `claude`, `codex`, `opencode`, `pi` | Harness-specific keys, written into that harness's entry verbatim. |

## Commands

Run `task --list` for available commands.

## Install

`scripts/installer.py` registers every server of `servers.yaml` into each harness found on PATH: Claude Code, Codex, OpenCode and Pi. It validates the manifest first and stops on any error.

| Command | Effect |
|---|---|
| `task install` | Check `requires`, then register every applicable server. |
| `task sync` | Install, update changed servers, and remove recorded servers the manifest no longer names. A second run changes nothing. |
| `task uninstall` | Remove the recorded entries, then clear the state. |
| `task doctor` | Also reports whether each installed harness has each server, reading config files only. |

Add `-- --dry-run` to `install` or `sync` (`task install -- --dry-run`) to print the plan per harness and write nothing, not even the state file or backups. Each line is `add`, `update`, `replace`, `remove`, `unchanged` or `skip`.

- A server is skipped, with the reason, when its `os` or `harnesses` exclude this machine or harness. A harness whose binary is not on PATH is skipped too.
- A server with a missing `requires` dependency is skipped with `MISSING: <dependency>` and its hint. The other servers continue and the exit status is non-zero.
- Claude Code and Pi are written with their own commands. Codex (`~/.codex/config.toml`) and OpenCode (`~/.config/opencode/opencode.jsonc`) are edited in place; the Codex edit keeps other tables and comments. OpenCode stops with a message if the file has comments, which an edit would drop.
- **State file:** `${XDG_STATE_HOME:-~/.local/state}/agent-mcp/state.json` records, per harness, the names this repo installed and a hash of each entry.
- **Backups:** before editing a file directly, the installer copies it to `<state dir>/backups/<harness>-<UTC timestamp>.<ext>`. Backups never go next to the config file.
- **Replace policy:** an entry with the same name that the state file does not record is removed and registered again from the manifest, then recorded. The plan shows it as `replace`.
- `uninstall` touches only recorded entries. An entry the manifest does not name, such as one added by hand, is never changed.

`task test` runs the installer tests. They use temporary directories and never start a harness command.

## Secrets

`secrets/secrets.sops.yaml` holds the Telegram API id and hash, encrypted with [sops](https://github.com/getsops/sops) and [age](https://github.com/FiloSottile/age); `secrets/.sops.yaml` holds the rules and `secrets/secrets.yaml.example` the plaintext template. Both tools run in one-off containers, so a host needs only Docker. Only low-value secrets belong in it: the repository is public and ciphertext stays in git history forever, so a later key leak would expose every past version.

The age private key is `age/key.txt` in the repository, mode 600 in a mode-700 `age/`. Git and Docker ignore it, and it is never committed. `~/.config/sops/age` is no longer used.

First machine (new key only): `task sops:generate-age-key` creates `age/key.txt`, never overwrites one, and prints the public key for `secrets/.sops.yaml`.

New machine: copy `age/key.txt` once, out of band, with `age/` at mode 700 and the file at mode 600. No new key is needed.

The loop, each step in your own terminal:

1. `task sops:decrypt` writes the plaintext `secrets/secrets.yaml` (ignored by git; do not commit it).
2. Edit `secrets/secrets.yaml`.
3. `task sops:encrypt` encrypts it to `secrets/secrets.sops.yaml` and removes the plaintext.

Other tasks: `task sops:get -- [--copy] NAME` shows one value, only in a terminal or on the clipboard; `task sops:updatekeys` re-encrypts to the recipients in `secrets/.sops.yaml`; `task sops:validate` needs no key and fails on an unencrypted store or a leftover plaintext file.

`git clean -fdx` deletes the ignored `age/key.txt`. Back the key up outside the repository: losing it makes `secrets/secrets.sops.yaml` undecryptable.

## Telegram

The `telegram` server is [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp), pinned to tag `v3.3.25` and built from its upstream Dockerfile. One container serves `http://127.0.0.1:8765/mcp` to all four harnesses, so Telegram sees one connection instead of one per client. Only Docker is needed on the host. Never install the PyPI package `telegram-mcp`: it is an unrelated project.

Exposed tools: read-only tools plus `send_message` and `reply_to_message` (`TELEGRAM_EXPOSED_TOOLS`). Set `TELEGRAM_EXPECTED_USERNAME` to refuse a session for the wrong account, and `TELEGRAM_TOOL_TIMEOUT_SECONDS` to change the tool timeout; both are passed to the container only when set in your shell.

Warning: the port is published on `127.0.0.1` only, and the endpoint has no authentication. Any local process running as you can read and send messages with your account.

Set up, once per machine:

1. `task sops:decrypt`, replace the `REPLACE_ME` placeholders in `secrets/secrets.yaml` with the real API id and hash from <https://my.telegram.org/apps>, then `task sops:encrypt`.
2. `task telegram:login`, then scan the QR code in Telegram under Settings > Devices > Link Desktop Device (and type the two-step verification password if asked). The task answers the script's prompts itself. The session string is converted into a session file and deleted; it is also printed on screen, so clear the terminal scrollback afterwards.
3. `task telegram:up`. `task doctor` reports whether the container is running and `/mcp` answers.
4. `task install` to register `telegram` in each harness.

Sessions are per machine. Telegram invalidates an auth key used from two IPs at once (`AuthKeyDuplicatedError`), so never copy a session between machines: each one runs its own QR login. Use `task telegram:down` to stop the server and `task telegram:logs` to follow its logs.

The session file holds account credentials. It lives in the `telegram-session` Docker volume, never in the repository, and is never committed. Voice transcripts are cached in the `telegram-transcripts` volume. To log in again, remove the volume with `docker volume rm agent-mcp_telegram-session` after `task telegram:down`.

`task telegram:login` and `task telegram:up` decrypt only the API id and hash into a mode-600 temporary file outside the repository, hand it to Compose, and delete it on exit. They refuse to run while the placeholders are still in `secrets/secrets.sops.yaml`.

## CI

`.github/workflows/ci.yml` runs on every push and pull request, needs no age key or repository secret, and decrypts nothing. It runs the same tasks you run locally:

- `task manifest:check`: `servers.yaml` matches its schema.
- `task test`: the installer test suite.
- `task sops:validate`: every `secrets/*.sops.yaml` is encrypted and no plaintext `secrets/secrets.yaml` is present.
- `task docker:config`: the Compose file is valid.
- gitleaks over the full git history.

## Project profile

This repository is initialized as a CLI foundation. Add verified project-specific build and test instructions as the implementation takes shape.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## Docker Compose

Every Compose call goes through `scripts/compose.sh`, which runs `compose.example.yaml` plus the ignored `compose.override.yaml` when it exists (put machine-specific settings there). The old local copy `compose.yaml` is no longer used; delete it.

| Task | Effect |
|---|---|
| `task docker` | build the images, then start the services |
| `task docker:build` / `docker:build-nocache` | build every image, tools included |
| `task docker:start` | start the services, leaving running ones alone (decrypts the Telegram credentials) |
| `task docker:recreate` | recreate the services so changed secrets or settings take effect |
| `task docker:stop` | stop the services, keeping containers and volumes |
| `task docker:down` | remove containers and network, keeping volumes |
| `task docker:restart` | `down`, then `start` |
| `task docker:ps` / `docker:logs` | list containers / follow logs |
| `task docker:config` | validate the Compose configuration |

No task removes a volume: `agent-mcp_telegram-session` holds this machine's Telegram login. The only long-running service is `telegram`; run `task telegram:login` once before the first `task docker:start`.
