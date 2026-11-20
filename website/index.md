# agent-mcp

![agent-mcp: a lavender and white plug beside the project name, its tagline and four pillars: one manifest, dry-run preview, sops and age secrets, verified in CI](assets/readme-banner.svg)

Declare every MCP server once and install it into Claude Code, Codex, OpenCode and Pi on macOS, Arch and Debian.

## What it does

- **One manifest.** `servers.yaml` declares every MCP server and the dependencies it needs. `servers.schema.json` defines the format, and `task manifest:check` validates it.
- **Installs into four harnesses.** `scripts/installer.py` registers every server into each harness found on `PATH`: Claude Code, Codex, OpenCode and Pi.
- **Dry-run preview.** `task install -- --dry-run` and `task sync -- --dry-run` print the plan per harness and write nothing, not even the state file or backups.
- **Undo.** `task uninstall` removes only the entries this repository recorded in its state file. Entries added by hand are never changed.
- **Secrets with sops and age.** `secrets/secrets.sops.yaml` holds the Telegram API id and hash, encrypted. Both tools run in one-off containers, so a host needs only Docker.
- **Verified in CI.** The manifest, the installer tests, the secrets store and the Compose file are checked on every push and pull request. See [CI and brand](ci-and-brand.md).

## Where to go next

- [Getting started](getting-started.md): prerequisites and the first install.
- [Operator guide](operator-guide.md): setup per machine, day-to-day commands, undo and troubleshooting.
- [Servers](servers.md): the servers the manifest declares.
- [CI and brand](ci-and-brand.md): what CI checks and where the brand assets come from.
