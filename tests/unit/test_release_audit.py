import ast
import json
import subprocess
import tomllib
from pathlib import Path

from scripts.release_audit import audit_repository


def _run(root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    files = {
        ".codex-plugin/plugin.json": json.dumps(
            {"name": "origin-com-automation", "version": "0.2.0"}
        ),
        ".gitignore": ".venv/\n*.opju\n",
        ".mcp.json": "{}\n",
        "CONTRIBUTING.md": "# Contributing\n",
        "LICENSE": "MIT License\n",
        "README.md": "# Origin COM Automation\n",
        "SECURITY.md": "# Security\n",
        "docs/REFERENCES.md": "# References\n",
        "pyproject.toml": '[project]\nname="origin-com-automation"\nversion="0.2.0"\n',
        "skills/origin-automation/SKILL.md": "---\nname: origin-automation\n---\n",
        "src/origin_com_automation/__init__.py": "__version__ = '0.2.0'\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _run(root, "init", "-b", "main")
    _run(root, "add", "--all")
    return root


def test_release_audit_accepts_minimal_safe_tracked_repository(tmp_path: Path):
    report = audit_repository(_repository(tmp_path))

    assert report["ok"] is True
    assert report["errors"] == []
    assert report["tracked_file_count"] == 11


def test_release_audit_rejects_origin_projects_personal_paths_and_secrets(tmp_path: Path):
    root = _repository(tmp_path)
    project = root / "private.opju"
    project.write_bytes(b"Origin project")
    personal_path = "C:" + "\\Users\\27421\\private"
    fake_token = "github_" + "pat_" + "abcdefghijklmnopqrstuvwxyz0123456789"
    (root / "README.md").write_text(
        f"{personal_path}\n{fake_token}\n",
        encoding="utf-8",
    )
    _run(root, "add", "--force", "private.opju", "README.md")

    report = audit_repository(root)
    codes = {item["code"] for item in report["errors"]}

    assert report["ok"] is False
    assert {"forbidden_extension", "personal_path", "secret_pattern"} <= codes


def test_release_audit_detects_manifest_package_version_drift(tmp_path: Path):
    root = _repository(tmp_path)
    manifest = root / ".codex-plugin" / "plugin.json"
    manifest.write_text(
        json.dumps({"name": "origin-com-automation", "version": "0.2.1"}),
        encoding="utf-8",
    )
    _run(root, "add", str(manifest.relative_to(root)))

    report = audit_repository(root)

    assert any(item["code"] == "version_mismatch" for item in report["errors"])


def test_v023_release_metadata_and_brand_assets_are_consistent():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    package = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(
        (root / "src" / "origin_com_automation" / "__init__.py").read_text(
            encoding="utf-8"
        )
    )
    runtime_version = next(
        node.value.value
        for node in runtime_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )
    interface = manifest["interface"]

    assert manifest["version"].startswith("0.2.3+")
    assert package["project"]["version"] == "0.2.3"
    assert runtime_version == "0.2.3"
    assert interface.get("brandColor") == "#DF5B3F"
    assert interface.get("composerIcon") == "./assets/origin-automation-composer.png"
    assert interface.get("logo") == "./assets/origin-automation-logo.png"
    for asset_path in (interface["composerIcon"], interface["logo"]):
        assert (root / asset_path.removeprefix("./")).is_file()


def test_release_audit_detects_runtime_package_version_drift(tmp_path: Path):
    root = _repository(tmp_path)
    runtime = root / "src" / "origin_com_automation" / "__init__.py"
    runtime.write_text("__version__ = '0.2.1'\n", encoding="utf-8")
    _run(root, "add", str(runtime.relative_to(root)))

    report = audit_repository(root)

    assert any(item["code"] == "version_mismatch" for item in report["errors"])
