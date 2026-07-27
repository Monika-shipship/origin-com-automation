import json
from pathlib import Path

from scripts.validate_distribution import validate_plugin, validate_skill


def test_repository_plugin_and_skill_distribution_is_valid():
    root = Path(__file__).resolve().parents[2]

    assert validate_plugin(root) == []


def test_mcp_uses_external_versioned_non_editable_runtime():
    root = Path(__file__).resolve().parents[2]
    mcp = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["origin-com-automation"]

    assert server["command"].lower() in {"powershell", "powershell.exe"}
    assert any("run_mcp.ps1" in str(item) for item in server["args"])
    bootstrap = (root / "scripts" / "bootstrap.ps1").read_text(encoding="utf-8").lower()
    launcher = (root / "scripts" / "run_mcp.ps1").read_text(encoding="utf-8").lower()
    runtime_path = (root / "scripts" / "runtime_path.ps1").read_text(encoding="utf-8").lower()
    assert "localappdata" in runtime_path
    assert "runtime" in runtime_path
    assert "pip install -e" not in bootstrap
    assert "pip install -e" not in launcher
    assert "runtime_path.ps1" in launcher
    assert "version" in runtime_path
    assert "preexistingtransient" in bootstrap
    assert "remove-item" in bootstrap


def test_skill_validation_rejects_unknown_frontmatter(tmp_path: Path):
    skill = tmp_path / "example"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill.\nunknown: true\n---\n",
        encoding="utf-8",
    )

    assert "unsupported frontmatter" in validate_skill(skill)[0]


def test_plugin_validation_rejects_missing_mcp_servers(tmp_path: Path):
    root = tmp_path / "sample-plugin"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / "skills" / "sample").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "sample-plugin",
                "version": "1.0.0",
                "description": "test",
                "skills": "./skills/",
                "mcpServers": "./.mcp.json",
                "interface": {
                    "displayName": "Test",
                    "shortDescription": "Test",
                    "longDescription": "Test",
                    "developerName": "Test",
                    "category": "Productivity",
                    "capabilities": ["Interactive"],
                    "defaultPrompt": ["Test"],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    (root / "skills" / "sample" / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Sample.\n---\n",
        encoding="utf-8",
    )

    assert ".mcp.json must define at least one MCP server" in validate_plugin(root)
