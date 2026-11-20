# Getting started

The [operator guide](operator-guide.md) is the full procedure. This page is the short path.

## Prerequisites

You need these tools on the machine ([the guide](operator-guide.md#tools) has the install command for macOS, Arch and Debian):

- git
- Python 3.11 or later
- [Task](https://taskfile.dev/installation/) 3
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker with Compose v2 and Buildx, because sops, age and Telegram run in containers

Install the harnesses you use. The installer skips any harness whose command (`claude`, `codex`, `opencode` or `pi`) is not on `PATH` and says so.

## First install

From the repository root:

```sh
git clone git@github.com:fnayou/agent-mcp.git && cd agent-mcp
task setup
task doctor
```

`task doctor` checks the prerequisites and reports whether each installed harness has each server. It reads configuration files only.

Preview the install. Nothing is written:

```sh
task install -- --dry-run
```

Each line says what happens to one server in one harness: `add`, `update`, `replace`, `remove`, `unchanged` or `skip`. When the plan is what you expect, install:

```sh
task install
```

A non-zero exit means at least one server was skipped for a missing dependency. The output names it and prints its hint. Restart open harness sessions so they load the new entries.

## Next steps

- The `telegram` server needs a one-time login on each machine: [Telegram: once per machine](operator-guide.md#telegram-once-per-machine).
- Secrets need the age key `age/key.txt`: [Another machine](operator-guide.md#another-machine-one-time-setup).
- To remove everything the installer added, see [Undo](operator-guide.md#undo).
