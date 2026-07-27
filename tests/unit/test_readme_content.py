from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGLISH = ROOT / "README.md"
CHINESE = ROOT / "README.zh-CN.md"
SERVER = ROOT / "src" / "origin_com_automation" / "server.py"
SECTION_MARKER = re.compile(r"<!-- section:([a-z0-9-]+) -->")
TOOL_NAME = re.compile(r'@strict_tool\(name="([a-z0-9_]+)"\)')
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXPECTED_SECTIONS = [
    "overview",
    "requirements",
    "setup",
    "quick-start",
    "session-modes",
    "tool-surface",
    "critical-path",
    "linked-data",
    "native-analysis",
    "architecture",
    "implementation",
    "figurespec-batch",
    "examples",
    "safety",
    "diagnostics",
    "tests",
    "update-uninstall",
    "scope-limits",
    "disclaimer",
    "references",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readmes_have_the_same_ordered_public_sections():
    assert ENGLISH.is_file()
    assert CHINESE.is_file()

    english_sections = SECTION_MARKER.findall(_read(ENGLISH))
    chinese_sections = SECTION_MARKER.findall(_read(CHINESE))

    assert english_sections == EXPECTED_SECTIONS
    assert chinese_sections == EXPECTED_SECTIONS


def test_readmes_link_languages_and_share_the_architecture_contract():
    english = _read(ENGLISH)
    chinese = _read(CHINESE)

    assert "[简体中文](README.zh-CN.md)" in english
    assert "[English](README.md)" in chinese
    for text in (english, chinese):
        assert "```mermaid" in text
        assert 'Codex["Codex / Codex App"]' in text
        assert 'MCP["Local Python MCP Server"]' in text
        assert 'Controller["Safety Controller"]' in text
        assert 'STA["Serialized STA COM Worker"]' in text
        assert 'Origin["Origin COM / LabTalk / X-Functions"]' in text
        assert 'Artifacts["Verified OPJU / Data / Graph Artifacts"]' in text


def test_readmes_document_the_same_editable_defaults_and_validation_evidence():
    english = _read(ENGLISH)
    chinese = _read(CHINESE)

    for text in (english, chinese):
        assert 'source_mode="linked"' in text
        assert 'source_mode="snapshot"' in text
        assert "origin_set_column_formula" in text
        assert 'backend="origin_native"' in text
        assert "create_operation=true" in text
        assert 'recalculate_mode="auto"' in text
        assert "origin_recover_session" in text
        assert "docs/VALIDATION-0.2.0.md" in text
        assert "docs/VALIDATION-0.2.1.md" in text


def test_readmes_include_equivalent_independence_and_risk_disclaimers():
    english = _read(ENGLISH)
    chinese = _read(CHINESE)

    assert "not affiliated with or endorsed by OriginLab" in english
    assert "back up important projects and source data" in english
    assert "review and validate outputs" in english
    assert "与 OriginLab 不存在隶属、授权或背书关系" in chinese
    assert "备份重要项目和源数据" in chinese
    assert "复核并验证输出" in chinese
    for text in (english, chinese):
        assert "[MIT License](LICENSE)" in text


def test_readmes_list_every_public_mcp_tool():
    tool_names = TOOL_NAME.findall(_read(SERVER))

    assert len(tool_names) == 45
    for text in (_read(ENGLISH), _read(CHINESE)):
        missing = [name for name in tool_names if name not in text]
        assert missing == []


def test_readme_local_links_resolve_to_repository_files():
    for readme in (ENGLISH, CHINESE):
        targets = MARKDOWN_LINK.findall(_read(readme))
        local_targets = [
            target.split("#", 1)[0]
            for target in targets
            if "://" not in target and not target.startswith("#")
        ]
        missing = [
            target
            for target in local_targets
            if not (ROOT / target).resolve().is_file()
        ]
        assert missing == []
