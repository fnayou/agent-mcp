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

## Project profile

This repository is initialized as a CLI foundation. Add verified project-specific build and test instructions as the implementation takes shape.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## Docker Compose

Run `task setup` to create ignored `compose.yaml` from the tracked example when it is missing. Edit the local file for machine-specific settings. Run `task docker:config` to validate the example.
