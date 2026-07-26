"""Fail-closed audit of files tracked for an origin-com-automation release."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED_FILES = {
    ".codex-plugin/plugin.json",
    ".gitignore",
    ".mcp.json",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs/REFERENCES.md",
    "pyproject.toml",
    "skills/origin-automation/SKILL.md",
}
FORBIDDEN_SUFFIXES = {
    ".opj",
    ".opju",
    ".ogw",
    ".ogwu",
    ".otw",
    ".otwu",
    ".xlsx",
    ".xls",
    ".csv",
    ".tsv",
    ".log",
}
FORBIDDEN_SEGMENTS = {
    ".venv",
    "venv",
    ".pytest_cache",
    "__pycache__",
    "outputs",
    "work",
    "artifacts",
    "superpowers",
}
MAX_FILE_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PERSONAL_PATH = re.compile(
    r"(?i)(?:[A-Z]:[\\/]+"
    + r"Users[\\/]+[A-Za-z0-9._-]+|"
    + r"/home/"
    + r"[A-Za-z0-9._-]+)"
)
SECRET_PATTERNS = {
    "github_token": re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "private_key": re.compile(r"-----BEGIN (?:(?:RSA|OPENSSH|EC|DSA) )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}


def _git_entries(root: Path) -> list[tuple[str, str]]:
    completed = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "--stage", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed: {detail}")
    entries: list[tuple[str, str]] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode = metadata.decode("ascii").split(" ", 1)[0]
        path = raw_path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        entries.append((mode, path))
    return entries


def _error(code: str, message: str, path: str | None = None) -> dict[str, str]:
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    return item


def _version_errors(root: Path) -> list[dict[str, str]]:
    try:
        manifest = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        runtime_tree = ast.parse(
            (root / "src/origin_com_automation/__init__.py").read_text(
                encoding="utf-8"
            )
        )
        manifest_version = str(manifest["version"]).split("+", 1)[0]
        package_version = str(project["project"]["version"])
        runtime_version = next(
            str(node.value.value)
            for node in runtime_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    except (
        KeyError,
        OSError,
        StopIteration,
        SyntaxError,
        UnicodeError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        return [_error("version_unreadable", f"Could not read release versions: {exc}")]
    if len({manifest_version, package_version, runtime_version}) != 1:
        return [
            _error(
                "version_mismatch",
                "Release versions differ: "
                f"manifest={manifest_version}, package={package_version}, runtime={runtime_version}",
            )
        ]
    return []


def audit_repository(root: str | Path) -> dict[str, Any]:
    """Audit tracked files only and return a stable JSON-safe report."""

    repository = Path(root).expanduser().resolve()
    entries = _git_entries(repository)
    tracked = {path for _, path in entries}
    errors: list[dict[str, str]] = []
    for required in sorted(REQUIRED_FILES - tracked):
        errors.append(_error("required_file_missing", "Required release file is not tracked", required))

    total_bytes = 0
    for mode, relative in entries:
        pure = PurePosixPath(relative)
        path = repository / Path(*pure.parts)
        if mode not in {"100644", "100755"}:
            errors.append(_error("unsafe_git_mode", f"Unsupported tracked mode {mode}", relative))
        if any(part.casefold() in FORBIDDEN_SEGMENTS for part in pure.parts):
            errors.append(_error("forbidden_directory", "Tracked path enters a forbidden directory", relative))
        if pure.suffix.casefold() in FORBIDDEN_SUFFIXES:
            errors.append(_error("forbidden_extension", "Tracked file type is forbidden", relative))
        if not path.is_file():
            errors.append(_error("tracked_file_missing", "Tracked file is missing", relative))
            continue
        size = path.stat().st_size
        total_bytes += size
        if size > MAX_FILE_BYTES:
            errors.append(_error("file_too_large", f"Tracked file is {size} bytes", relative))
        if pure.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(_error("non_utf8_text", "Tracked text file is not UTF-8", relative))
            continue
        if PERSONAL_PATH.search(text):
            errors.append(_error("personal_path", "Tracked text contains a personal absolute path", relative))
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(_error("secret_pattern", f"Tracked text matches {name}", relative))
    if REQUIRED_FILES <= tracked:
        errors.extend(_version_errors(repository))
    return {
        "schema_version": 1,
        "ok": not errors,
        "tracked_file_count": len(entries),
        "tracked_total_bytes": total_bytes,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit_repository(args.root)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif report["ok"]:
        print(f"Release audit passed: {report['tracked_file_count']} tracked files")
    else:
        for item in report["errors"]:
            location = f" ({item['path']})" if "path" in item else ""
            print(f"{item['code']}{location}: {item['message']}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
