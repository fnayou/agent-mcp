# fnayou/agent-mcp

Declare every MCP server once and install it into Claude Code, Codex, OpenCode and Pi on macOS, Arch and Debian.

## Getting started

Install [Task](https://taskfile.dev/) and run `task setup`, then `task doctor`.

## Commands

Run `task --list` for available commands.

## Project profile

This repository is initialized as a CLI foundation. Add verified project-specific build and test instructions as the implementation takes shape.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md).

## Docker Compose

Run `task setup` to create ignored `compose.yaml` from the tracked example when it is missing. Edit the local file for machine-specific settings. Run `task docker:config` to validate the example.
