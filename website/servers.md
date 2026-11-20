# Servers

`servers.yaml` declares every server. Unless a server sets `os` or `harnesses`, it applies to all four harnesses (Claude Code, Codex, OpenCode and Pi) on every supported OS. The field reference is in the [README](https://github.com/fnayou/agent-mcp#server-manifest).

| Server | Transport | Harnesses | OS | Needs |
|---|---|---|---|---|
| [`playwright`](#playwright) | `stdio` | all | all | the agent-browser skill |
| [`playwright-auth`](#playwright-auth) | `stdio` | all | all | the agent-browser skill |
| [`telegram`](#telegram) | `http` | all | all | Docker |
| [`safari-mcp`](#safari-mcp) | `stdio` | all | macOS only | `/usr/bin/safaridriver` |

## playwright

An agent-only headless browser with an in-memory profile, for general web work.

- **Transport:** `stdio`, started by `~/.agents/skills/agent-browser/scripts/agent-browser-mcp`, with a startup timeout of 30 seconds.
- **Harnesses:** all four.
- **Needs:** the `agent-browser` skill from [fnayou/agent-skills](https://github.com/fnayou/agent-skills). `task install` skips the server with `MISSING: agent-browser` and a hint when the script is absent.
- **Codex:** the manifest sets `approval_mode: approve` for `browser_evaluate`, `browser_navigate`, `browser_click` and `browser_close`.

## playwright-auth

An agent-only headed browser with a persistent profile, for sites the user signs in to. One agent at a time.

- **Transport:** `stdio`, started by the same `agent-browser-mcp` script with the argument `auth`, and a startup timeout of 30 seconds.
- **Harnesses:** all four.
- **Needs:** the `agent-browser` skill, as for `playwright`.

## telegram

Telegram account access through one shared HTTP server in Compose. It has read-only tools plus `send_message` and `reply_to_message`.

- **Transport:** `http`, at `http://127.0.0.1:8765/mcp`. One container serves all four harnesses, so Telegram sees one connection instead of one per client.
- **Harnesses:** all four.
- **Needs:** `docker`. The Compose service `telegram` must be running: `task telegram:up`.
- **Source:** [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp), pinned to tag `v3.3.25` and built from its upstream Dockerfile.
- **Setup:** once per machine, with its own QR login. See [Telegram: once per machine](operator-guide.md#telegram-once-per-machine).

!!! warning "No authentication"
    The port is published on `127.0.0.1` only, and the endpoint has no authentication. Any local process running as you can read and send messages with your account.

## safari-mcp

Safari compatibility checks through Safari's built-in MCP server. One session at a time.

- **Transport:** `stdio`, started with `/usr/bin/safaridriver --mcp`.
- **OS:** macOS only (`os: [darwin]`). The binary ships with macOS.
- **Harnesses:** all four.
- **Setup:** enable Develop > Allow Remote Automation in Safari once.
