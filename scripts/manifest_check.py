# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "jsonschema>=4.23",
#     "pyyaml>=6.0",
# ]
# ///
"""Validate servers.yaml against servers.schema.json and its cross-references."""
from pathlib import Path
import json
import sys

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def location(path):
    return "/".join(str(part) for part in path) or "(root)"


def message(error):
    # `not: {required: [field]}` marks a field the server's transport does not accept.
    if error.validator == "not" and list(error.validator_value) == ["required"]:
        field = error.validator_value["required"][0]
        return f"'{field}' is not allowed with transport '{error.instance.get('transport')}'"
    return error.message


def check(manifest_path, schema_path):
    try:
        manifest = yaml.safe_load(manifest_path.read_text())
    except (OSError, yaml.YAMLError) as error:
        return [f"{manifest_path.name}: cannot read: {error}"]
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors = [
        f"{location(error.absolute_path)}: {message(error)}"
        for error in sorted(validator.iter_errors(manifest), key=lambda e: list(map(str, e.absolute_path)))
    ]
    if errors:
        return errors
    # JSON Schema cannot check that a server's requires names a declared dependency.
    declared = set(manifest.get("requires", {}))
    for name, server in manifest["servers"].items():
        for dependency in server.get("requires", []):
            if dependency not in declared:
                errors.append(f"servers/{name}/requires: '{dependency}' is not declared under requires")
    return errors


def main(argv):
    manifest_path = Path(argv[1]) if len(argv) > 1 else ROOT / "servers.yaml"
    errors = check(manifest_path, ROOT / "servers.schema.json")
    for error in errors:
        print(f"INVALID: {error}")
    if errors:
        return 1
    print(f"OK: {manifest_path.name} matches servers.schema.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
