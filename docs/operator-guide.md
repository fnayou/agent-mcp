# Operator guide

This guide is for the person who installs and runs agent-mcp on a machine. It lists what to prepare, which commands to run in which order, how to check each step, and how to undo it.

The guide is kept in step with the code. Any change to a task, a prerequisite, a server or an operator step updates this file in the same pull request (see [Keeping this guide current](#keeping-this-guide-current)).

## Contents

1. [What agent-mcp changes on a machine](#what-agent-mcp-changes-on-a-machine)
2. [Where to run commands](#where-to-run-commands)
3. [Prerequisites](#prerequisites)
4. [First machine: one-time setup](#first-machine-one-time-setup)
5. [Another machine: one-time setup](#another-machine-one-time-setup)
6. [Telegram: once per machine](#telegram-once-per-machine)
7. [Install the servers into the harnesses](#install-the-servers-into-the-harnesses)
8. [Day to day](#day-to-day)
9. [Undo](#undo)
10. [Where things live](#where-things-live)
11. [Troubleshooting](#troubleshooting)
12. [Keeping this guide current](#keeping-this-guide-current)

## What agent-mcp changes on a machine

| What | Where | Changed by |
|---|---|---|
| Claude Code MCP entries | `~/.claude.json` (user scope) | `task install`, `sync`, `uninstall`, through `claude mcp` |
| Codex MCP entries | `~/.codex/config.toml` | the same tasks, by editing the file |
| OpenCode MCP entries | `~/.config/opencode/opencode.jsonc` | the same tasks, by editing the file |
| Pi MCP entries | `~/.pi/agent/mcp.json` | the same tasks, through `pi mcp` |
| Installer state and backups | `${XDG_STATE_HOME:-~/.local/state}/agent-mcp/` | the same tasks |
| age private key | `age/key.txt` in the repository (ignored by git and Docker; `~/.config/sops/age` is no longer used) | you (`task sops:generate-age-key` or a copy) |
| Plaintext secrets (only while editing) | `secrets/secrets.yaml` (ignored by git) | `task sops:decrypt`; removed by `task sops:encrypt` |
| Docker images | `agent-mcp-tools:*`, `agent-mcp-telegram:*`, `agent-mcp-telegram-login:*` | built on first use |
| Docker volumes | `agent-mcp_telegram-session`, `agent-mcp_telegram-transcripts` | `task telegram:login`, `task telegram:up` |
| Telegram container | `telegram`, port `127.0.0.1:8765` | `task telegram:up` / `telegram:down`, or `task docker:start` / `docker:stop` |

Nothing else outside the repository is written. Entries the manifest does not name (for example a server you added by hand) are never changed.

## Where to run commands

Run every command from the repository root.

- **Interactive commands, or commands that show secrets, run in your own terminal**: `task sops:generate-age-key`, `task sops:decrypt`, `task sops:encrypt`, `task sops:get`, `task telegram:login`. They need a keyboard or show a QR code, and their output must not end up in an AI assistant's transcript.
- **Every other command** (`task doctor`, `task install`, `task telegram:up`, ...) can run in your terminal or through an assistant, for example with the `!` prefix in Claude Code, so the assistant can read the output.

## Prerequisites

### Tools

| Tool | Why | macOS | Arch | Debian |
|---|---|---|---|---|
| git | clone the repository | Xcode Command Line Tools or `brew install git` | `pacman -S git` | `apt install git` |
| Python 3.11 or later | `task doctor`, `task setup` | `brew install python` | `pacman -S python` | `apt install python3` |
| [Task](https://taskfile.dev/installation/) 3 | runs every command | `brew install go-task` | `pacman -S go-task` (the binary is `go-task`; alias it to `task`) | the install script from taskfile.dev |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | runs the Python scripts with locked dependencies | `brew install uv` | `pacman -S uv` | the install script from astral.sh |
| Docker with Compose v2 and Buildx | sops, age and Telegram run in containers | Docker Desktop (or another engine that provides `docker compose`) | `pacman -S docker docker-compose docker-buildx`, then enable the service and join the `docker` group | Docker's own apt repository: `docker-ce`, `docker-compose-plugin`, `docker-buildx-plugin`, then join the `docker` group |

The Docker engine must be running before any `sops:*` (except `sops:validate`), `telegram:*` or `doctor` command.

Versions tested: macOS with Docker Desktop 4.99, Docker Compose v5.7, Task 3.54, uv 0.13, Python 3.15. Arch and Debian are supported by the code but not yet tested end to end; record the first run here.

### Harnesses

Install the harnesses you use; the installer skips any harness whose command is not on `PATH` and says so.

| Harness | Command on PATH |
|---|---|
| Claude Code | `claude` |
| Codex | `codex` |
| OpenCode | `opencode` |
| Pi | `pi` |

OpenCode: the installer refuses to edit `opencode.jsonc` when it contains comments, because the edit would drop them. Remove the comments first, or keep OpenCode out of the install. The installer rewrites the file with 2-space indentation.

### Per-server dependencies

`task install` checks these and skips a server whose dependency is missing, with a hint.

| Server | Needs | OS |
|---|---|---|
| `playwright`, `playwright-auth` | the agent-browser skill at `~/.agents/skills/agent-browser/scripts/agent-browser-mcp` ([fnayou/agent-skills](https://github.com/fnayou/agent-skills)) | all |
| `safari-mcp` | `/usr/bin/safaridriver` (ships with macOS) | macOS only |
| `telegram` | `docker`, and the Telegram container running ([Telegram](#telegram-once-per-machine)) | all |

The source of truth is `servers.yaml`. When it gains a server, add its row here.

### Things to have at hand

- **Telegram API id and hash**: log in at <https://my.telegram.org/apps>, open "API development tools", and create an application. Note the `api_id` (a number) and `api_hash`. One pair serves every machine.
- **Your phone with Telegram**, for the QR login on each machine.
- **A safe place for the age private key** (a password manager, for example). Losing the key makes `secrets/secrets.sops.yaml` unreadable, and `git clean -fdx` deletes `age/key.txt`; leaking it exposes every past version of the secrets, which stay in the public git history.

## First machine: one-time setup

This repository's `secrets/secrets.sops.yaml` is already encrypted for the current key. Skip this section if you hold that key; go to [Another machine](#another-machine-one-time-setup). Follow it only for a new key: a fork, or a lost key.

1. Clone and prepare:
   ```sh
   git clone git@github.com:fnayou/agent-mcp.git && cd agent-mcp
   task setup
   ```
2. In your own terminal, generate the age key. It refuses to overwrite an existing key.
   ```sh
   task sops:generate-age-key
   ```
   Check: `age/` is mode 700 and `age/key.txt` is mode 600. Store a copy of `age/key.txt` in your safe place now: `git clean -fdx` deletes it.
3. Put the printed public key (`age1...`) in `secrets/.sops.yaml` in place of the old one. Then create the secrets file again for the new key: delete `secrets/secrets.sops.yaml`, copy `secrets/secrets.yaml.example` to `secrets/secrets.yaml`, enter real values for `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`, and run `task sops:encrypt`, which also removes the plaintext. Commit `secrets/.sops.yaml` and `secrets/secrets.sops.yaml` and open a pull request.
4. Run `task doctor` and continue with [Telegram](#telegram-once-per-machine).

## Another machine: one-time setup

Every machine uses the same age key; no new key is needed.

1. Install the [prerequisites](#prerequisites).
2. Clone and prepare:
   ```sh
   git clone git@github.com:fnayou/agent-mcp.git && cd agent-mcp
   task setup
   ```
3. Copy `age/key.txt` from your safe place, out of band, never through git:
   ```sh
   mkdir -p -m 700 age
   # place key.txt there, then:
   chmod 600 age/key.txt
   ```
   `~/.config/sops/age` is no longer read. Back the key up: `git clean -fdx` deletes it.
4. Run `task doctor`. Expect `OK: age key (age/key.txt, mode 600)`, `OK: secrets are encrypted; no plaintext at rest` and `OK: secrets/secrets.sops.yaml decrypts`.
5. Continue with [Telegram](#telegram-once-per-machine). The API id and hash are already in `secrets/secrets.sops.yaml`; skip step 1 there.

## Telegram: once per machine

Each machine logs in on its own. Telegram invalidates an auth key used from two IP addresses at once (`AuthKeyDuplicatedError`), so never copy a session between machines.

Security: the server listens on `127.0.0.1:8765` only, and has no authentication. Any local process running as you can read your chats and send messages from your account. It exposes the read-only tools plus `send_message` and `reply_to_message`.

1. **Set the real API id and hash** (first machine only). In your own terminal:
   ```sh
   task sops:decrypt
   ```
   Replace both `REPLACE_ME` values in `secrets/secrets.yaml` with your `api_id` and `api_hash`, save, then run `task sops:encrypt`, which encrypts the file and removes the plaintext. Commit `secrets/secrets.sops.yaml` (it stays encrypted) and open a pull request.
2. **Log in.** In your own terminal:
   ```sh
   task telegram:login
   ```
   The first run builds two images, which takes a few minutes. Then:
   - press Enter at the label prompt;
   - answer `y` when asked to update `.env`;
   - on your phone, open Telegram > Settings > Devices > Link Desktop Device, and scan the QR code.

   The session is stored in the `agent-mcp_telegram-session` volume, and the temporary session string is deleted.
3. **Start the server:**
   ```sh
   task telegram:up
   ```
4. **Check:** `task doctor` shows `OK: telegram container is running` and `OK: http://127.0.0.1:8765/mcp answers`.

Optional settings, read from your shell when the container starts: `TELEGRAM_EXPECTED_USERNAME` (refuse a session for another account) and `TELEGRAM_TOOL_TIMEOUT_SECONDS` (default 55).

The credentials reach the container through a temporary mode-600 file outside the repository, deleted when the command ends. It holds only `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. `telegram:login` and `telegram:up` refuse to run while `secrets/secrets.sops.yaml` still holds `REPLACE_ME`.

## Install the servers into the harnesses

Do this after Telegram, so `telegram` is registered too. You can install before Telegram; run `task sync` later to add it.

1. **Back up the harness configs** the first time. The installer backs up the files it edits directly (Codex, OpenCode, Pi passthrough), but Claude Code and Pi are changed through their own commands:
   ```sh
   mkdir -p ~/agent-mcp-backup
   cp ~/.claude.json ~/.codex/config.toml ~/.config/opencode/opencode.jsonc ~/.pi/agent/mcp.json ~/agent-mcp-backup/ 2>/dev/null
   ```
2. **Preview.** Nothing is written, not even the state file:
   ```sh
   task install -- --dry-run
   ```
   Read every line. Each says what happens to one server in one harness:

   | Action | Meaning |
   |---|---|
   | `add` | new entry |
   | `replace` | an entry with this name exists but this repo did not install it; it is removed and registered again from the manifest |
   | `update` | an entry this repo installed has changed in the manifest |
   | `unchanged` | nothing to do |
   | `remove` | (sync only) recorded entry the manifest no longer names |
   | `skip` | not for this OS or harness, harness not installed, or a dependency missing (with a hint) |

   On a machine that already has hand-made entries with the same names, expect `replace` for them on the first run. Stop here if a line is not what you expect.
3. **Install:**
   ```sh
   task install
   ```
   A non-zero exit means at least one server was skipped for a missing dependency; the output names it and its hint.
4. **Check:** `task doctor` prints `OK: <harness> has <server>` for each one. Restart open harness sessions so they load the new entries.

## Day to day

| When | Run |
|---|---|
| Before working on the repository | `task doctor` |
| After `git pull` changed `servers.yaml` | `task sync -- --dry-run`, then `task sync` |
| Telegram after a reboot | nothing: the container restarts with Docker unless you stopped it |
| Stop or start Telegram | `task telegram:down` / `task telegram:up` |
| Stop or start every service | `task docker:stop` / `task docker:start` (`docker:down` removes the containers, never the volumes) |
| Rebuild the images | `task docker:build`, then `task docker:recreate` |
| List containers | `task docker:ps` |
| Telegram logs | `task telegram:logs` (Ctrl-C to stop following) |
| Change a secret | `task sops:decrypt`, edit `secrets/secrets.yaml`, `task sops:encrypt`, all in your own terminal; then `task docker:recreate` |
| Read one secret | `task sops:get -- NAME` in your own terminal (`-- --copy NAME` copies it to the clipboard) |
| Change who can decrypt | edit `secrets/.sops.yaml`, then `task sops:updatekeys` |
| Check the secrets store | `task sops:validate` (no key needed) |
| See every task | `task --list` |

## Undo

- **Remove what agent-mcp installed** in the harnesses (only recorded entries; others stay):
  ```sh
  task uninstall
  ```
- **Restore a harness config** from the installer's backups, newest last:
  ```sh
  ls ~/.local/state/agent-mcp/backups/
  cp ~/.local/state/agent-mcp/backups/codex-<timestamp>.toml ~/.codex/config.toml
  ```
  Or from your own copy in `~/agent-mcp-backup/`.
- **Stop Telegram:** `task telegram:down` (keeps the session).
- **Log Telegram out of this machine:** `task telegram:down`, then `docker volume rm agent-mcp_telegram-session`. Also end the session on your phone under Settings > Devices. Run `task telegram:login` to log in again.
- **Remove the transcript cache:** `docker volume rm agent-mcp_telegram-transcripts` (after `task telegram:down`).

## Where things live

| Item | Location | In git |
|---|---|---|
| Server list | `servers.yaml`, format in `servers.schema.json` | yes |
| Encrypted secrets | `secrets/secrets.sops.yaml`, rules in `secrets/.sops.yaml`, template `secrets/secrets.yaml.example` | yes (encrypted) |
| Plaintext secrets, while editing | `secrets/secrets.yaml` | never |
| age private key | `age/key.txt` (back it up: `git clean -fdx` deletes it) | never |
| Installer state | `~/.local/state/agent-mcp/state.json` | no |
| Installer backups | `~/.local/state/agent-mcp/backups/` | no |
| Telegram session | Docker volume `agent-mcp_telegram-session` | never |
| Telegram transcripts | Docker volume `agent-mcp_telegram-transcripts` | never |
| Compose file | `compose.example.yaml`, run through `scripts/compose.sh` | yes |
| Local Compose settings | `compose.override.yaml`, optional, merged when present | no |

## Troubleshooting

Messages from `task doctor` and `task install`:

| Message | Fix |
|---|---|
| `MISSING: git` / `python3` / `uv` | install the tool ([Prerequisites](#prerequisites)) |
| `NOT CHECKED: Compose config; Docker CLI is missing.` | install Docker |
| `NOT CHECKED: Compose config; Docker Compose plugin is missing.` | install the Compose v2 plugin |
| `INVALID: Compose config; ...` | run `task docker:config` and fix `compose.example.yaml` or `compose.override.yaml` |
| `compose.yaml is no longer used; ...` (from `task setup`) | move any local settings to `compose.override.yaml`, then delete `compose.yaml` |
| `MISSING: age key; ...` | copy `age/key.txt` ([Another machine](#another-machine-one-time-setup)) or, on the very first machine only, `task sops:generate-age-key` |
| `INVALID: age/key.txt is not mode 600; ...` | `chmod 600 age/key.txt` |
| `ERROR: ... is not SOPS-encrypted ...` | restore `secrets/secrets.sops.yaml` from git, or run `task sops:encrypt` |
| `ERROR: plaintext secrets/secrets.yaml present ...` | `task sops:encrypt` (it removes the plaintext), or delete the file if you do not need it |
| `INVALID: secrets/secrets.sops.yaml does not decrypt with age/key.txt` | wrong `age/key.txt`, or Docker not running |
| `secrets/secrets.yaml already exists; refusing to overwrite unsaved edits. ...` | `task sops:encrypt` to save the edits (it removes the plaintext), or remove `secrets/secrets.yaml` to discard them, then run `task sops:decrypt` again |
| `refusing to overwrite existing key: age/key.txt` | a key exists; `task sops:generate-age-key` never replaces it |
| `sops:get: stdout is not a terminal; ...` | run `task sops:get` in your own terminal, or add `--copy` |
| `NOT CHECKED: <harness>; '<cmd>' is not on PATH` | install the harness, or ignore it |
| `NOT REGISTERED: <harness> lacks <server>; run task install` | run `task install` |
| `WARNING: telegram container is not running; ...` | `task telegram:login` once, then `task telegram:up` |
| `WARNING: http://127.0.0.1:8765/mcp does not answer` | `task telegram:logs`; check that port 8765 is free |
| `MISSING: <dependency>` during install | follow the hint printed below it |
| `secrets/secrets.sops.yaml still holds placeholders; ...` | `task sops:decrypt`, edit, `task sops:encrypt` ([Telegram step 1](#telegram-once-per-machine)) |
| `AuthKeyDuplicatedError` in the Telegram logs | the session is in use elsewhere: log this machine out and log in again ([Undo](#undo)) |

## Keeping this guide current

This guide is part of the code. A pull request that changes any of the following updates this guide in the same pull request:

- a task in `Taskfile.yml` that an operator runs;
- a prerequisite, a supported OS, or a tested version;
- a server in `servers.yaml`, or one of its dependencies;
- a file, volume, port or path written outside the repository;
- a message printed by `task doctor` or the installer.

When you run the guide on a new OS or version, update "Versions tested" under [Prerequisites](#prerequisites).
