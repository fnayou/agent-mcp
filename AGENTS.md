# Agent instructions: fnayou/agent-mcp

Project profile: CLI. Declare every MCP server once and install it into Claude Code, Codex, OpenCode and Pi on macOS, Arch and Debian.

## Commands

Use `task --list` to see available commands. Run `task setup` once, then `task doctor` before project work.

## Working rules

`docs/operator-guide.md` is the human guide. A change to an operator task, a prerequisite, a server in `servers.yaml`, a path, volume or port outside the repository, or a message from `task doctor` or the installer updates that guide in the same pull request.

Preserve user changes and existing files. Keep credentials out of source control and logs. Use focused changes and Conventional Commits. Check `docs/agents/` for issue-tracker, triage-label, and domain-doc conventions when those files exist.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `fnayou/agent-mcp`, managed with `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
