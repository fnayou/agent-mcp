# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "jsonschema>=4.23",
#     "pyyaml>=6.0",
#     "tomlkit>=0.13",
# ]
# ///
"""Tests for scripts/installer.py. No harness CLI starts and the real home directory is never read."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import io
import json
import sys
import tempfile
import tomllib
import unittest

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import installer  # noqa: E402

MANIFEST = ROOT / "servers.yaml"
LAUNCHER = ".agents/skills/agent-browser/scripts/agent-browser-mcp"
STAMP = "20260102T030405Z"


def expected_claude(home):
    launcher = f"{home}/{LAUNCHER}"
    return {
        "playwright": {"type": "stdio", "command": launcher, "args": [], "env": {}},
        "playwright-auth": {"type": "stdio", "command": launcher, "args": ["auth"], "env": {}},
        "safari-mcp": {"type": "stdio", "command": "/usr/bin/safaridriver", "args": ["--mcp"], "env": {}},
    }


def expected_codex(home):
    launcher = f"{home}/{LAUNCHER}"
    approve = {"approval_mode": "approve"}
    return {
        "playwright": {
            "command": launcher,
            "startup_timeout_sec": 30,
            "tools": {
                "browser_evaluate": approve,
                "browser_navigate": approve,
                "browser_click": approve,
                "browser_close": approve,
            },
        },
        "playwright-auth": {"command": launcher, "args": ["auth"], "startup_timeout_sec": 30},
        "safari-mcp": {"command": "/usr/bin/safaridriver", "args": ["--mcp"]},
    }


def expected_opencode(home):
    launcher = f"{home}/{LAUNCHER}"
    return {
        "playwright": {"type": "local", "command": [launcher], "timeout": {"startup": 30000}},
        "playwright-auth": {"type": "local", "command": [launcher, "auth"], "timeout": {"startup": 30000}},
        "safari-mcp": {"type": "local", "command": ["/usr/bin/safaridriver", "--mcp"]},
    }


def expected_pi(home):
    launcher = f"{home}/{LAUNCHER}"
    manifest = yaml.safe_load(MANIFEST.read_text())["servers"]
    description = {name: server["description"] for name, server in manifest.items()}
    return [
        ["pi", "mcp", "add", "playwright", "--description", description["playwright"], "--", launcher],
        ["pi", "mcp", "add", "playwright-auth", "--description", description["playwright-auth"], "--", launcher, "auth"],
        ["pi", "mcp", "add", "safari-mcp", "--description", description["safari-mcp"], "--", "/usr/bin/safaridriver", "--mcp"],
    ]


class FakeCli:
    """Stands in for the claude and pi commands by editing their config files under the temporary home."""

    def __init__(self, home):
        self.home = home
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        tool, verb = argv[0], argv[2]
        if tool == "claude":
            path, key = self.home / ".claude.json", "mcpServers"
        elif tool == "pi":
            path, key = self.home / ".pi" / "agent" / "mcp.json", "mcpServers"
        else:
            raise AssertionError(f"unexpected command: {argv}")
        data = json.loads(path.read_text()) if path.exists() else {}
        servers = data.setdefault(key, {})
        if tool == "claude" and verb == "add-json":
            servers[argv[5]] = json.loads(argv[6])
        elif tool == "claude" and verb == "remove":
            del servers[argv[5]]
        elif tool == "pi" and verb == "add":
            servers[argv[3]] = self.pi_entry(argv[4:])
        elif tool == "pi" and verb == "remove":
            del servers[argv[3]]
        else:
            raise AssertionError(f"unexpected command: {argv}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    @staticmethod
    def pi_entry(rest):
        entry = {"description": rest[rest.index("--description") + 1]}
        if "--url" in rest:
            entry["url"] = rest[rest.index("--url") + 1]
        else:
            command = rest[rest.index("--") + 1:]
            entry.update(command=command[0], args=command[1:])
        return entry


class InstallerCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = Path(directory.name)
        self.home = self.tmp / "home"
        self.state_dir = self.tmp / "state" / "agent-mcp"
        launcher = self.home / LAUNCHER
        launcher.parent.mkdir(parents=True)
        launcher.touch()
        self.cli = FakeCli(self.home)
        self.binaries = set(installer.HARNESSES)
        self.machine = frozenset({"darwin"})

    def env(self):
        return installer.Env(
            home=self.home,
            state_dir=self.state_dir,
            machine=self.machine,
            run=self.cli,
            which=lambda binary: f"/bin/{binary}" if binary in self.binaries else None,
            now=lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )

    def invoke(self, command, manifest=MANIFEST, dry_run=False):
        out = io.StringIO()
        with redirect_stdout(out):
            code = installer.run(self.env(), command, manifest, dry_run)
        return code, out.getvalue()

    def manifest(self, servers, requires=None):
        path = self.tmp / "servers.yaml"
        document = {"schema_version": 1, "servers": servers}
        if requires:
            document["requires"] = requires
        path.write_text(yaml.safe_dump(document))
        return path

    def claude(self):
        return json.loads((self.home / ".claude.json").read_text())["mcpServers"]

    def codex_path(self):
        return self.home / ".codex" / "config.toml"

    def codex(self):
        return tomllib.loads(self.codex_path().read_text()).get("mcp_servers", {})

    def opencode_path(self):
        return self.home / ".config" / "opencode" / "opencode.jsonc"

    def opencode(self):
        return json.loads(self.opencode_path().read_text())["mcp"]["servers"]

    def pi(self):
        return json.loads((self.home / ".pi" / "agent" / "mcp.json").read_text())["mcpServers"]

    def state(self):
        return json.loads((self.state_dir / "state.json").read_text())["harnesses"]

    def seed(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def snapshot(self):
        return {str(path): path.read_bytes() for path in self.tmp.rglob("*") if path.is_file()}


class EquivalenceTest(InstallerCase):
    def setUp(self):
        super().setUp()
        self.code, self.output = self.invoke("install")

    def test_install_succeeds(self):
        self.assertEqual(self.code, 0, self.output)

    def test_claude_entries_match_the_live_config(self):
        self.assertEqual(self.claude(), expected_claude(self.home))

    def test_claude_is_registered_in_user_scope(self):
        add = [call for call in self.cli.calls if call[:3] == ["claude", "mcp", "add-json"]]
        self.assertEqual(len(add), 3)
        self.assertTrue(all(call[3:5] == ["--scope", "user"] for call in add))

    def test_codex_entries_match_the_live_config(self):
        self.assertEqual(self.codex(), expected_codex(self.home))

    def test_opencode_entries_match_the_live_config(self):
        self.assertEqual(self.opencode(), expected_opencode(self.home))

    def test_pi_commands_match_the_live_config(self):
        pi_calls = [call for call in self.cli.calls if call[0] == "pi"]
        self.assertEqual(pi_calls, expected_pi(self.home))

    def test_state_records_every_installed_name_with_a_hash(self):
        state = self.state()
        for harness in installer.HARNESSES:
            self.assertEqual(set(state[harness]), {"playwright", "playwright-auth", "safari-mcp"})
            self.assertTrue(all(len(value) == 64 for value in state[harness].values()))


class DryRunTest(InstallerCase):
    def test_install_dry_run_writes_nothing(self):
        before = self.snapshot()
        code, output = self.invoke("install", dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.cli.calls, [])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.state_dir.exists())
        self.assertIn("add", output)

    def test_sync_dry_run_writes_nothing_over_existing_files(self):
        self.seed(self.codex_path(), "# mine\n[model]\nname = 'x'\n")
        self.seed(self.opencode_path(), '{"theme": "dark"}')
        self.invoke("install")
        self.invoke("uninstall")
        self.seed(self.codex_path(), "# mine\n")
        before = self.snapshot()
        calls = len(self.cli.calls)
        code, _ = self.invoke("sync", dry_run=True)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.cli.calls), calls)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_shows_an_unowned_entry_as_replace(self):
        self.seed(self.home / ".claude.json", json.dumps({"mcpServers": {"playwright": {"type": "stdio", "command": "/old"}}}))
        _, output = self.invoke("install", dry_run=True)
        self.assertRegex(output, r"replace\s+playwright\n")
        self.assertRegex(output, r"add\s+playwright-auth\n")


class IdempotenceTest(InstallerCase):
    def test_sync_after_install_changes_nothing(self):
        self.invoke("install")
        before = self.snapshot()
        calls = len(self.cli.calls)
        code, output = self.invoke("sync")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.cli.calls), calls)
        self.assertEqual(self.snapshot(), before)
        self.assertNotRegex(output, r"\b(add|update|replace|remove)\b")
        self.assertIn("unchanged", output)

    def test_install_twice_changes_nothing(self):
        self.invoke("install")
        before = self.snapshot()
        self.invoke("install")
        self.assertEqual(self.snapshot(), before)


class ReplaceTest(InstallerCase):
    def test_unowned_claude_entry_is_removed_and_registered_again(self):
        self.seed(self.home / ".claude.json", json.dumps({"mcpServers": {"playwright": {"type": "stdio", "command": "/old"}}}))
        self.invoke("install")
        self.assertIn(["claude", "mcp", "remove", "--scope", "user", "playwright"], self.cli.calls)
        self.assertEqual(self.claude(), expected_claude(self.home))
        self.assertIn("playwright", self.state()["claude"])

    def test_unowned_codex_entry_is_replaced(self):
        self.seed(self.codex_path(), '[mcp_servers.playwright]\ncommand = "/old"\nextra = 1\n')
        self.invoke("install")
        self.assertEqual(self.codex(), expected_codex(self.home))

    def test_unowned_opencode_entry_is_replaced(self):
        self.seed(self.opencode_path(), json.dumps({"mcp": {"servers": {"playwright": {"type": "local", "command": ["/old"]}}}}))
        self.invoke("install")
        self.assertEqual(self.opencode(), expected_opencode(self.home))


class UninstallTest(InstallerCase):
    def setUp(self):
        super().setUp()
        foreign = {"type": "stdio", "command": "/bin/solidcraft"}
        self.seed(self.home / ".claude.json", json.dumps({"mcpServers": {"solidcraft": foreign}}))
        self.seed(self.codex_path(), '# keep me\n[mcp_servers.solidcraft]\ncommand = "/bin/solidcraft"\n')
        self.seed(self.opencode_path(), json.dumps({"mcp": {"servers": {"solidcraft": {"type": "local", "command": ["/bin/solidcraft"]}}}}))
        self.seed(self.home / ".pi" / "agent" / "mcp.json", json.dumps({"mcpServers": {"solidcraft": {"command": "/bin/solidcraft"}}}))
        self.invoke("install")
        self.code, self.output = self.invoke("uninstall")

    def test_uninstall_removes_every_recorded_entry_and_nothing_else(self):
        self.assertEqual(self.code, 0, self.output)
        self.assertEqual(set(self.claude()), {"solidcraft"})
        self.assertEqual(set(self.codex()), {"solidcraft"})
        self.assertEqual(set(self.opencode()), {"solidcraft"})
        self.assertEqual(set(self.pi()), {"solidcraft"})

    def test_uninstall_clears_the_state(self):
        self.assertEqual(self.state(), {})

    def test_uninstall_keeps_codex_comments(self):
        self.assertIn("# keep me", self.codex_path().read_text())

    def test_uninstall_ignores_an_entry_the_state_does_not_record(self):
        self.invoke("install")
        self.seed(self.home / ".claude.json", json.dumps({"mcpServers": {"playwright": {"type": "stdio", "command": "/hand-made"}}}))
        (self.state_dir / "state.json").write_text(json.dumps({"version": 1, "harnesses": {}}))
        calls = len(self.cli.calls)
        self.invoke("uninstall")
        self.assertEqual(len(self.cli.calls), calls)
        self.assertEqual(self.claude()["playwright"]["command"], "/hand-made")


class SyncTest(InstallerCase):
    def server(self, command, **extra):
        return {"description": "test server", "transport": "stdio", "command": command, **extra}

    def test_sync_adds_updates_and_removes(self):
        before = self.manifest({"alpha": self.server("/bin/a"), "beta": self.server("/bin/b")})
        self.invoke("install", before)
        after = self.manifest({"alpha": self.server("/bin/a", args=["--changed"]), "gamma": self.server("/bin/g")})
        code, output = self.invoke("sync", after)
        self.assertEqual(code, 0, output)
        self.assertRegex(output, r"update\s+alpha")
        self.assertRegex(output, r"remove\s+beta")
        self.assertRegex(output, r"add\s+gamma")
        self.assertEqual(set(self.claude()), {"alpha", "gamma"})
        self.assertEqual(self.claude()["alpha"]["args"], ["--changed"])
        self.assertEqual(set(self.codex()), {"alpha", "gamma"})
        self.assertEqual(set(self.opencode()), {"alpha", "gamma"})
        self.assertEqual(set(self.pi()), {"alpha", "gamma"})
        self.assertEqual(set(self.state()["codex"]), {"alpha", "gamma"})

    def test_install_does_not_remove_recorded_entries(self):
        self.invoke("install", self.manifest({"alpha": self.server("/bin/a"), "beta": self.server("/bin/b")}))
        self.invoke("install", self.manifest({"alpha": self.server("/bin/a")}))
        self.assertEqual(set(self.claude()), {"alpha", "beta"})

    def test_sync_registers_an_entry_the_user_deleted(self):
        manifest = self.manifest({"alpha": self.server("/bin/a")})
        self.invoke("install", manifest)
        self.seed(self.home / ".claude.json", json.dumps({"mcpServers": {}}))
        _, output = self.invoke("sync", manifest)
        self.assertRegex(output, r"add\s+alpha")
        self.assertEqual(set(self.claude()), {"alpha"})

    def test_http_server_renders_per_harness(self):
        manifest = self.manifest({"web": {"description": "web", "transport": "http", "url": "http://localhost:9000/mcp"}})
        self.invoke("install", manifest)
        self.assertEqual(self.claude()["web"], {"type": "http", "url": "http://localhost:9000/mcp"})
        self.assertEqual(self.codex()["web"], {"url": "http://localhost:9000/mcp"})
        self.assertEqual(self.opencode()["web"], {"type": "remote", "url": "http://localhost:9000/mcp"})
        self.assertIn(["pi", "mcp", "add", "web", "--description", "web", "--url", "http://localhost:9000/mcp"], self.cli.calls)

    def test_env_and_passthrough_are_rendered(self):
        manifest = self.manifest({"envy": self.server(
            "${HOME}/bin/envy",
            env={"MODE": "fast"},
            claude={"alwaysLoad": True},
            codex={"tools": {"run": {"approval_mode": "approve"}}},
            opencode={"enabled": False},
        )})
        self.invoke("install", manifest)
        command = f"{self.home}/bin/envy"
        self.assertEqual(self.claude()["envy"], {"type": "stdio", "command": command, "args": [], "env": {"MODE": "fast"}, "alwaysLoad": True})
        self.assertEqual(self.codex()["envy"], {"command": command, "env": {"MODE": "fast"}, "tools": {"run": {"approval_mode": "approve"}}})
        self.assertEqual(self.opencode()["envy"], {"type": "local", "command": [command], "environment": {"MODE": "fast"}, "enabled": False})
        self.assertIn(["pi", "mcp", "add", "envy", "--description", "test server", "--env", "MODE=fast", "--", command], self.cli.calls)


class FilterTest(InstallerCase):
    def test_os_filter_skips_a_server_and_says_so(self):
        self.machine = frozenset({"arch"})
        code, output = self.invoke("install")
        self.assertEqual(code, 0, output)
        self.assertRegex(output, r"skip\s+safari-mcp: os is darwin")
        self.assertEqual(set(self.claude()), {"playwright", "playwright-auth"})
        self.assertEqual(set(self.codex()), {"playwright", "playwright-auth"})

    def test_harness_filter_skips_a_server_and_says_so(self):
        manifest = self.manifest({
            "only-codex": {"description": "d", "transport": "stdio", "command": "/bin/x", "harnesses": ["codex"]},
        })
        _, output = self.invoke("install", manifest)
        self.assertRegex(output, r"skip\s+only-codex: harnesses is codex")
        self.assertEqual(set(self.codex()), {"only-codex"})
        self.assertFalse((self.home / ".claude.json").exists())
        self.assertFalse(self.opencode_path().exists())
        self.assertEqual(self.cli.calls, [])

    def test_a_filtered_server_is_not_checked_for_dependencies(self):
        self.machine = frozenset({"arch"})
        manifest = self.manifest(
            {"mac-only": {"description": "d", "transport": "stdio", "command": "/bin/x", "os": ["darwin"], "requires": ["gone"]}},
            requires={"gone": {"check": {"command": "no-such-tool"}, "hint": "install it"}},
        )
        code, _ = self.invoke("install", manifest)
        self.assertEqual(code, 0)

    def test_detect_machine(self):
        self.assertEqual(installer.detect_machine("Darwin", ""), {"darwin"})
        self.assertEqual(installer.detect_machine("Linux", 'ID=arch\nNAME="Arch Linux"\n'), {"arch"})
        self.assertEqual(installer.detect_machine("Linux", "ID=ubuntu\nID_LIKE=debian\n"), {"debian"})
        self.assertEqual(installer.detect_machine("Linux", 'ID="cachyos"\nID_LIKE="arch"\n'), {"arch"})
        self.assertEqual(installer.detect_machine("Linux", "ID=fedora\n"), frozenset())


class MissingTest(InstallerCase):
    def test_missing_harness_binary_is_skipped_without_error(self):
        self.binaries.discard("codex")
        code, output = self.invoke("install")
        self.assertEqual(code, 0, output)
        self.assertIn("codex: skipped, 'codex' is not on PATH", output)
        self.assertFalse(self.codex_path().exists())
        self.assertNotIn("codex", self.state())
        self.assertEqual(set(self.claude()), set(expected_claude(self.home)))

    def test_every_harness_missing_is_not_an_error(self):
        self.binaries.clear()
        code, _ = self.invoke("install")
        self.assertEqual(code, 0)
        self.assertEqual(self.cli.calls, [])

    def test_missing_dependency_skips_the_server_and_fails_the_run(self):
        (self.home / LAUNCHER).unlink()
        code, output = self.invoke("install")
        self.assertEqual(code, 1)
        self.assertIn("MISSING: agent-browser", output)
        self.assertIn("Install the agent-browser skill", output)
        self.assertEqual(set(self.claude()), {"safari-mcp"})
        self.assertEqual(set(self.codex()), {"safari-mcp"})

    def test_missing_command_dependency_is_reported(self):
        manifest = self.manifest(
            {"needs-tool": {"description": "d", "transport": "stdio", "command": "/bin/x", "requires": ["tool"]}},
            requires={"tool": {"check": {"command": "no-such-tool"}, "hint": "install no-such-tool"}},
        )
        code, output = self.invoke("install", manifest)
        self.assertEqual(code, 1)
        self.assertIn("MISSING: tool. install no-such-tool", output)

    def test_missing_dependency_keeps_the_recorded_entry_on_sync(self):
        self.invoke("install")
        (self.home / LAUNCHER).unlink()
        code, _ = self.invoke("sync")
        self.assertEqual(code, 1)
        self.assertIn("playwright", self.claude())
        self.assertIn("playwright", self.state()["claude"])

    def test_invalid_manifest_stops_before_any_change(self):
        path = self.tmp / "bad.yaml"
        path.write_text("schema_version: 1\nservers:\n  Bad_Name: {description: d, transport: stdio, command: /x}\n")
        code, output = self.invoke("install", path)
        self.assertEqual(code, 1)
        self.assertIn("INVALID:", output)
        self.assertEqual(self.cli.calls, [])
        self.assertFalse(self.state_dir.exists())


class CodexFileTest(InstallerCase):
    TEXT = (
        "# my codex settings\n"
        'model = "gpt-5" # the default\n'
        "\n"
        "# trusted projects\n"
        '[projects."/work/x"]\n'
        'trust_level = "trusted"\n'
        "\n"
        "[mcp_servers.solidcraft]\n"
        'command = "/bin/solidcraft"\n'
    )

    def test_unrelated_tables_and_comments_survive_install_and_uninstall(self):
        self.seed(self.codex_path(), self.TEXT)
        self.invoke("install")
        installed = self.codex_path().read_text()
        for line in self.TEXT.splitlines():
            self.assertIn(line, installed)
        self.invoke("uninstall")
        self.assertEqual(tomllib.loads(self.codex_path().read_text()), tomllib.loads(self.TEXT))
        self.assertIn("# my codex settings", self.codex_path().read_text())
        self.assertIn("# trusted projects", self.codex_path().read_text())

    def test_tool_approvals_become_subtables(self):
        self.invoke("install")
        self.assertIn("[mcp_servers.playwright.tools.browser_evaluate]", self.codex_path().read_text())


class OpenCodeFileTest(InstallerCase):
    def test_other_keys_survive(self):
        self.seed(self.opencode_path(), json.dumps({"theme": "dark", "mcp": {"other": 1, "servers": {"solidcraft": {"type": "local", "command": ["s"]}}}}))
        self.invoke("install")
        data = json.loads(self.opencode_path().read_text())
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["mcp"]["other"], 1)
        self.assertIn("solidcraft", data["mcp"]["servers"])

    def test_comments_stop_the_edit_and_leave_the_file_alone(self):
        text = '{\n  // my theme\n  "theme": "dark"\n}\n'
        self.seed(self.opencode_path(), text)
        code, output = self.invoke("install")
        self.assertEqual(code, 1)
        self.assertIn("contains comments", output)
        self.assertEqual(self.opencode_path().read_text(), text)
        self.assertNotIn("opencode", self.state_dir.joinpath("state.json").read_text() if self.state_dir.exists() else "")

    def test_comment_markers_inside_strings_are_not_comments(self):
        self.seed(self.opencode_path(), json.dumps({"url": "http://example.com/a//b"}))
        code, _ = self.invoke("install")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.opencode_path().read_text())["url"], "http://example.com/a//b")


class BackupTest(InstallerCase):
    def setUp(self):
        super().setUp()
        self.codex_text = "# mine\n[model]\nname = 'x'\n"
        self.opencode_text = '{"theme": "dark"}'
        self.seed(self.codex_path(), self.codex_text)
        self.seed(self.opencode_path(), self.opencode_text)
        self.seed(self.home / ".pi" / "agent" / "mcp.json", "{}")
        manifest = self.manifest({"alpha": {"description": "d", "transport": "stdio", "command": "/bin/a", "pi": {"timeout": 5}}})
        self.code, _ = self.invoke("install", manifest)

    def test_backups_land_in_the_state_dir_with_the_original_content(self):
        backups = self.state_dir / "backups"
        self.assertEqual((backups / f"codex-{STAMP}.toml").read_text(), self.codex_text)
        self.assertEqual((backups / f"opencode-{STAMP}.jsonc").read_text(), self.opencode_text)
        self.assertTrue((backups / f"pi-{STAMP}.json").exists())

    def test_the_pi_passthrough_is_merged(self):
        self.assertEqual(self.pi()["alpha"]["timeout"], 5)

    def test_no_backup_is_written_next_to_a_config_file(self):
        self.assertEqual(sorted(path.name for path in self.codex_path().parent.iterdir()), ["config.toml"])
        self.assertEqual(sorted(path.name for path in self.opencode_path().parent.iterdir()), ["opencode.jsonc"])
        self.assertEqual(sorted(path.name for path in (self.home / ".pi" / "agent").iterdir()), ["mcp.json"])

    def test_one_backup_per_file_per_run(self):
        self.assertEqual(len(list((self.state_dir / "backups").iterdir())), 3)

    def test_a_file_that_did_not_exist_needs_no_backup(self):
        for path in (self.codex_path(), self.opencode_path()):
            path.unlink()
        for path in (self.state_dir / "backups").iterdir():
            path.unlink()
        (self.state_dir / "state.json").unlink()
        self.invoke("install", self.tmp / "servers.yaml")
        self.assertEqual([path.name for path in (self.state_dir / "backups").iterdir() if path.name.startswith(("codex", "opencode"))], [])


class StatusTest(InstallerCase):
    def test_status_reads_files_and_never_runs_a_command(self):
        _, before = self.invoke("status")
        self.assertIn("NOT REGISTERED: claude lacks playwright", before)
        self.invoke("install")
        calls = len(self.cli.calls)
        self.binaries.discard("pi")
        code, after = self.invoke("status")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.cli.calls), calls)
        self.assertIn("OK: claude has playwright", after)
        self.assertIn("OK: codex has safari-mcp", after)
        self.assertIn("NOT CHECKED: pi; 'pi' is not on PATH", after)

    def test_status_skips_servers_that_do_not_apply(self):
        self.machine = frozenset({"debian"})
        _, output = self.invoke("status")
        self.assertNotIn("safari-mcp", output)

    def test_status_never_prints_env_values(self):
        manifest = self.manifest({"envy": {"description": "d", "transport": "stdio", "command": "/bin/e", "env": {"TOKEN": "s3cret"}}})
        self.invoke("install", manifest)
        _, output = self.invoke("status", manifest)
        self.assertNotIn("s3cret", output)


if __name__ == "__main__":
    unittest.main(verbosity=1)
