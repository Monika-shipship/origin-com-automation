"""Validate the checked-out Codex plugin and its Skill for CI packaging."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _json_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name} is not readable JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return None
    return value


def validate_skill(skill_root: Path) -> list[str]:
    errors: list[str] = []
    path = skill_root / "SKILL.md"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"SKILL.md is not readable: {exc}"]
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if match is None:
        return ["SKILL.md must start with closed YAML frontmatter"]
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"SKILL.md frontmatter is invalid YAML: {exc}"]
    if not isinstance(frontmatter, dict):
        return ["SKILL.md frontmatter must be an object"]
    unknown = set(frontmatter) - {"name", "description", "license", "allowed-tools", "metadata"}
    if unknown:
        errors.append(f"SKILL.md has unsupported frontmatter fields: {sorted(unknown)}")
    name = frontmatter.get("name")
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name) or len(name) > 64:
        errors.append("SKILL.md name must be hyphen-case and at most 64 characters")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append("SKILL.md description must contain 1 to 1024 characters")
    return errors


def validate_plugin(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = _json_object(root / ".codex-plugin" / "plugin.json", errors)
    mcp = _json_object(root / ".mcp.json", errors)
    if manifest is not None:
        for field in ("name", "version", "description", "skills", "mcpServers", "interface"):
            if field not in manifest:
                errors.append(f"plugin.json is missing {field}")
        if manifest.get("name") != root.name:
            errors.append("plugin.json name must match the repository folder")
        version = manifest.get("version")
        if not isinstance(version, str) or SEMVER.fullmatch(version) is None:
            errors.append("plugin.json version must be strict semver")
        if manifest.get("skills") != "./skills/":
            errors.append("plugin.json skills must be ./skills/")
        if manifest.get("mcpServers") != "./.mcp.json":
            errors.append("plugin.json mcpServers must be ./.mcp.json")
        interface = manifest.get("interface")
        if not isinstance(interface, dict):
            errors.append("plugin.json interface must be an object")
        else:
            for field in (
                "displayName",
                "shortDescription",
                "longDescription",
                "developerName",
                "category",
                "capabilities",
                "defaultPrompt",
            ):
                if not interface.get(field):
                    errors.append(f"plugin.json interface is missing {field}")
    if mcp is not None:
        servers = mcp.get("mcpServers")
        if not isinstance(servers, dict) or not servers:
            errors.append(".mcp.json must define at least one MCP server")
        else:
            for name, server in servers.items():
                if not isinstance(server, dict):
                    errors.append(f"MCP server {name} must be an object")
                    continue
                if not isinstance(server.get("command"), str) or not server["command"]:
                    errors.append(f"MCP server {name} must define command")
                if not isinstance(server.get("args"), list):
                    errors.append(f"MCP server {name} must define args as an array")
    skills_root = root / "skills"
    if not skills_root.is_dir():
        errors.append("skills directory is missing")
    else:
        for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            errors.extend(f"{skill_root.name}: {message}" for message in validate_skill(skill_root))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    errors = validate_plugin(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Plugin and Skill distribution validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
