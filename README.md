# fnayou/agent-mcp

Declare every MCP server once and install it into Claude Code, Codex, OpenCode and Pi on macOS, Arch and Debian.

## Getting started

Install [Task](https://taskfile.dev/) and [uv](https://docs.astral.sh/uv/), then run `task setup` and `task doctor`.

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

`secrets.sops.yaml` holds the Telegram API id and hash, encrypted with [sops](https://github.com/getsops/sops) and [age](https://github.com/FiloSottile/age). Both tools run in containers, so a host needs only Docker. Only low-value secrets belong in it: the repository is public and ciphertext stays in git history forever, so a later key leak would expose every past version.

First machine: run `task secrets:keygen`. It writes `~/.config/sops/age/keys.txt` (override the directory with `SOPS_AGE_KEY_DIR`) and refuses to overwrite an existing key. Put the printed public key in `.sops.yaml`.

New machine: copy `keys.txt` once, out of band, to `~/.config/sops/age/keys.txt` with the directory at mode 700 and the file at mode 600. No new key is needed.

- `task secrets:edit` edits `secrets.sops.yaml`.
- `task secrets:decrypt` prints the decrypted file to stdout. `task secrets:decrypt OUT=<path>` writes it to a mode-600 file and refuses any path inside the repository.

Back up the key. Losing it makes `secrets.sops.yaml` undecryptable.

## Project profile

This repository is initialized as a CLI foundation. Add verified project-specific build and test instructions as the implementation takes shape.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## Docker Compose

Run `task setup` to create ignored `compose.yaml` from the tracked example when it is missing. Edit the local file for machine-specific settings. Run `task docker:config` to validate the example.
