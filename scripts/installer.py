# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "jsonschema>=4.23",
#     "pyyaml>=6.0",
#     "tomlkit>=0.13",
# ]
# ///
"""Register the servers of servers.yaml into Claude Code, Codex, OpenCode and Pi."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import argparse
import copy
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib

import tomlkit
import yaml

import manifest_check

ROOT = Path(__file__).resolve().parent.parent
HARNESSES = ("claude", "codex", "opencode", "pi")


class InstallError(Exception):
    pass


@dataclass
class Env:
    home: Path
    state_dir: Path
    machine: frozenset
    run: Callable  # argv -> object with returncode
    which: Callable  # binary name -> path or None
    now: Callable  # () -> aware datetime


def run_process(argv):
    try:
        return subprocess.run(argv, capture_output=True, text=True)
    except OSError as error:
        raise InstallError(f"cannot run {argv[0]}: {error.strerror}")


def detect_machine(system, os_release):
    """Map the platform to the manifest's `os` values: darwin, arch, debian."""
    if system == "Darwin":
        return frozenset({"darwin"})
    ids = set()
    for line in os_release.splitlines():
        key, _, value = line.partition("=")
        if key in ("ID", "ID_LIKE"):
            ids.update(value.strip().strip("\"'").split())
    return frozenset(ids & {"arch", "debian"})


def default_env():
    home = Path.home()
    state_home = os.environ.get("XDG_STATE_HOME")
    try:
        os_release = Path("/etc/os-release").read_text()
    except OSError:
        os_release = ""
    return Env(
        home=home,
        state_dir=(Path(state_home) if state_home else home / ".local" / "state") / "agent-mcp",
        machine=detect_machine(platform.system(), os_release),
        run=run_process,
        which=shutil.which,
        now=lambda: datetime.now(timezone.utc),
    )


# Data helpers

def expand(value, home):
    """Expand ${HOME}, and nothing else, in every string of a manifest value."""
    if isinstance(value, str):
        return value.replace("${HOME}", str(home))
    if isinstance(value, list):
        return [expand(item, home) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, home) for key, item in value.items()}
    return value


def merge(base, extra):
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def digest(entry):
    return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def has_comments(text):
    in_string = escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "/" and text[index + 1:index + 2] in ("/", "*"):
            return True
    return False


def load_json(path, jsonc=False):
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise InstallError(f"cannot read {path}: {error.strerror}")
    if not text.strip():
        return {}
    if jsonc and has_comments(text):
        raise InstallError(f"{path} contains comments that the installer would drop; remove them or edit the file by hand")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise InstallError(f"cannot parse {path}: {error}")
    if not isinstance(data, dict):
        raise InstallError(f"{path} does not hold a JSON object")
    return data


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def table(data, *keys):
    """Descend through nested objects, treating a missing level as empty."""
    for key in keys:
        data = data.get(key, {})
        if not isinstance(data, dict):
            raise InstallError(f"'{key}' is not an object")
    return data


# Harnesses

class Harness:
    name = binary = ext = ""

    def __init__(self, env):
        self.env = env
        self.backed_up = False

    @property
    def path(self):
        raise NotImplementedError

    def backup(self):
        """Copy the config file to the state directory once, before the first direct edit."""
        if self.backed_up or not self.path.exists():
            return
        stamp = self.env.now().strftime("%Y%m%dT%H%M%SZ")
        target = self.env.state_dir / "backups" / f"{self.name}-{stamp}{self.ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, target)
        self.backed_up = True

    def cli(self, argv, name):
        # The argv can carry env values, so a failure reports only its first words.
        if self.env.run(argv).returncode:
            raise InstallError(f"{' '.join(argv[:3])} failed for '{name}'")


class Claude(Harness):
    name, binary, ext = "claude", "claude", ".json"

    @property
    def path(self):
        return self.env.home / ".claude.json"

    def render(self, name, server):
        if server["transport"] == "stdio":
            entry = {
                "type": "stdio",
                "command": server["command"],
                "args": list(server.get("args", [])),
                "env": dict(server.get("env", {})),
            }
        else:
            entry = {"type": "http", "url": server["url"]}
        return merge(entry, server.get("claude", {}))

    def names(self):
        return set(table(load_json(self.path), "mcpServers"))

    def put(self, name, entry):
        self.cli(["claude", "mcp", "add-json", "--scope", "user", name, json.dumps(entry)], name)

    def drop(self, name):
        self.cli(["claude", "mcp", "remove", "--scope", "user", name], name)


class Codex(Harness):
    name, binary, ext = "codex", "codex", ".toml"

    @property
    def path(self):
        return self.env.home / ".codex" / "config.toml"

    def render(self, name, server):
        entry = {}
        if server["transport"] == "stdio":
            entry["command"] = server["command"]
            if server.get("args"):
                entry["args"] = list(server["args"])
            if server.get("env"):
                entry["env"] = dict(server["env"])
        else:
            entry["url"] = server["url"]
        if "startup_timeout_sec" in server:
            entry["startup_timeout_sec"] = server["startup_timeout_sec"]
        return merge(entry, server.get("codex", {}))

    def read(self):
        try:
            return self.path.read_text()
        except FileNotFoundError:
            return ""
        except OSError as error:
            raise InstallError(f"cannot read {self.path}: {error.strerror}")

    def names(self):
        try:
            return set(tomllib.loads(self.read()).get("mcp_servers", {}))
        except tomllib.TOMLDecodeError as error:
            raise InstallError(f"cannot parse {self.path}: {error}")

    def edit(self, change):
        doc = tomlkit.parse(self.read())
        change(doc)
        self.backup()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(tomlkit.dumps(doc))

    def put(self, name, entry):
        def add(doc):
            if "mcp_servers" not in doc:
                doc["mcp_servers"] = tomlkit.table(is_super_table=True)
            doc["mcp_servers"][name] = entry
        self.edit(add)

    def drop(self, name):
        self.edit(lambda doc: doc["mcp_servers"].__delitem__(name))


class OpenCode(Harness):
    name, binary, ext = "opencode", "opencode", ".jsonc"

    @property
    def path(self):
        return self.env.home / ".config" / "opencode" / "opencode.jsonc"

    def render(self, name, server):
        if server["transport"] == "stdio":
            entry = {"type": "local", "command": [server["command"], *server.get("args", [])]}
            if server.get("env"):
                entry["environment"] = dict(server["env"])
        else:
            entry = {"type": "remote", "url": server["url"]}
        if "startup_timeout_sec" in server:
            entry["timeout"] = {"startup": server["startup_timeout_sec"] * 1000}
        return merge(entry, server.get("opencode", {}))

    def names(self):
        return set(table(load_json(self.path, jsonc=True), "mcp", "servers"))

    def edit(self, change):
        data = load_json(self.path, jsonc=True)
        change(data.setdefault("mcp", {}).setdefault("servers", {}))
        self.backup()
        write_json(self.path, data)

    def put(self, name, entry):
        self.edit(lambda servers: servers.__setitem__(name, entry))

    def drop(self, name):
        self.edit(lambda servers: servers.pop(name))


class Pi(Harness):
    name, binary, ext = "pi", "pi", ".json"

    @property
    def path(self):
        return self.env.home / ".pi" / "agent" / "mcp.json"

    def render(self, name, server):
        entry = {"description": server["description"]}
        if server["transport"] == "stdio":
            entry["command"] = server["command"]
            entry["args"] = list(server.get("args", []))
            entry["env"] = dict(server.get("env", {}))
        else:
            entry["url"] = server["url"]
        if server.get("pi"):
            entry["passthrough"] = server["pi"]
        return entry

    def argv(self, name, entry):
        argv = ["pi", "mcp", "add", name, "--description", entry["description"]]
        if "url" in entry:
            return argv + ["--url", entry["url"]]
        for key, value in entry["env"].items():
            argv += ["--env", f"{key}={value}"]
        return argv + ["--", entry["command"], *entry["args"]]

    def names(self):
        return set(table(load_json(self.path), "mcpServers"))

    def put(self, name, entry):
        self.cli(self.argv(name, entry), name)
        if "passthrough" in entry:
            data = load_json(self.path)
            servers = data.setdefault("mcpServers", {})
            servers[name] = merge(servers.get(name, {}), entry["passthrough"])
            self.backup()
            write_json(self.path, data)

    def drop(self, name):
        self.cli(["pi", "mcp", "remove", name], name)


def harnesses(env):
    return [Claude(env), Codex(env), OpenCode(env), Pi(env)]


# State

def state_path(env):
    return env.state_dir / "state.json"


def load_state(env):
    state = load_json(state_path(env))
    state.setdefault("harnesses", {})
    return state


def save_state(env, state):
    write_json(state_path(env), {"version": 1, "harnesses": state["harnesses"]})


# Planning

def skip_reason(server, harness, env):
    if "os" in server and not env.machine & set(server["os"]):
        return f"os is {', '.join(server['os'])}"
    if "harnesses" in server and harness.name not in server["harnesses"]:
        return f"harnesses is {', '.join(server['harnesses'])}"
    return None


def missing_dependencies(env, manifest, server):
    missing = []
    for dependency in server.get("requires", []):
        requirement = manifest["requires"][dependency]
        check = expand(requirement["check"], env.home)
        present = Path(check["path"]).exists() if "path" in check else env.which(check["command"]) is not None
        if not present:
            missing.append((dependency, requirement["hint"]))
    return missing


def report(action, name, note=""):
    print(f"  {action:<9} {name}" + (f": {note}" if note else ""))


def reconcile(env, manifest, harness, recorded, prune, dry_run):
    """Bring one harness in line with the manifest; return (new record, failed)."""
    existing = harness.names()
    new = dict(recorded)
    wanted = set()
    failed = False
    for name, server in manifest["servers"].items():
        reason = skip_reason(server, harness, env)
        if reason:
            report("skip", name, reason)
            continue
        wanted.add(name)
        missing = missing_dependencies(env, manifest, server)
        for dependency, hint in missing:
            report("skip", name, f"MISSING: {dependency}. {hint}")
        if missing:
            failed = True
            continue
        server = expand(server, env.home)
        entry = harness.render(name, server)
        entry_hash = digest(entry)
        if name in existing and name in recorded:
            action = "unchanged" if recorded[name] == entry_hash else "update"
        else:
            action = "replace" if name in existing else "add"
        report(action, name)
        if action == "unchanged" or dry_run:
            continue
        try:
            if name in existing:
                harness.drop(name)
            harness.put(name, entry)
        except InstallError as error:
            print(f"  ERROR: {error}")
            failed = True
            continue
        new[name] = entry_hash
    if prune:
        for name in sorted(set(recorded) - wanted):
            report("remove", name)
            if dry_run:
                continue
            try:
                if name in existing:
                    harness.drop(name)
            except InstallError as error:
                print(f"  ERROR: {error}")
                failed = True
                continue
            del new[name]
    return new, failed


def installed(env, harness):
    if env.which(harness.binary):
        return True
    print(f"{harness.name}: skipped, '{harness.binary}' is not on PATH")
    return False


def load_manifest(path):
    errors = manifest_check.check(path, ROOT / "servers.schema.json")
    for error in errors:
        print(f"INVALID: {error}")
    if errors:
        raise InstallError(f"{path.name} is invalid; nothing was changed")
    manifest = yaml.safe_load(path.read_text())
    manifest.setdefault("requires", {})
    return manifest


def apply(env, manifest, prune, dry_run):
    state = load_state(env)
    failed = False
    for harness in harnesses(env):
        if not installed(env, harness):
            continue
        print(f"{harness.name}:")
        try:
            new, bad = reconcile(env, manifest, harness, state["harnesses"].get(harness.name, {}), prune, dry_run)
        except InstallError as error:
            print(f"  ERROR: {error}")
            failed = True
            continue
        failed |= bad
        if dry_run:
            continue
        if new:
            state["harnesses"][harness.name] = new
        else:
            state["harnesses"].pop(harness.name, None)
        save_state(env, state)
    return 1 if failed else 0


def uninstall(env):
    state = load_state(env)
    failed = False
    for harness in harnesses(env):
        recorded = state["harnesses"].get(harness.name)
        if not recorded:
            continue
        if not installed(env, harness):
            print(f"  {len(recorded)} recorded entries kept in the state file")
            continue
        print(f"{harness.name}:")
        try:
            existing = harness.names()
            for name in sorted(recorded):
                report("remove", name)
                if name in existing:
                    harness.drop(name)
                del recorded[name]
        except InstallError as error:
            print(f"  ERROR: {error}")
            failed = True
        if recorded:
            state["harnesses"][harness.name] = recorded
        else:
            del state["harnesses"][harness.name]
        save_state(env, state)
    return 1 if failed else 0


def status(env, manifest):
    """Report whether each applicable server is registered, reading config files only."""
    failed = False
    for harness in harnesses(env):
        if not env.which(harness.binary):
            print(f"NOT CHECKED: {harness.name}; '{harness.binary}' is not on PATH")
            continue
        try:
            existing = harness.names()
        except InstallError as error:
            print(f"INVALID: {harness.name}; {error}")
            failed = True
            continue
        for name, server in manifest["servers"].items():
            if skip_reason(server, harness, env):
                continue
            if name in existing:
                print(f"OK: {harness.name} has {name}")
            else:
                print(f"NOT REGISTERED: {harness.name} lacks {name}; run task install")
    return 1 if failed else 0


def run(env, command, manifest_path, dry_run=False):
    try:
        manifest = load_manifest(manifest_path)
        if command == "uninstall":
            return uninstall(env)
        if command == "status":
            return status(env, manifest)
        return apply(env, manifest, prune=command == "sync", dry_run=dry_run)
    except InstallError as error:
        print(f"ERROR: {error}")
        return 1


def main(argv, env=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("install", "register every applicable server; leave other entries alone"),
        ("sync", "install, then remove recorded entries that the manifest no longer names"),
    ):
        commands.add_parser(name, help=help_text).add_argument(
            "--dry-run", action="store_true", help="print the plan per harness and write nothing"
        )
    commands.add_parser("uninstall", help="remove only the entries recorded in the state file")
    commands.add_parser("status", help="report which servers each installed harness has, from config files only")
    args = parser.parse_args(argv)
    return run(env or default_env(), args.command, ROOT / "servers.yaml", getattr(args, "dry_run", False))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
