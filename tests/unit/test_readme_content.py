from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
ENGLISH = ROOT / "README.md"
CHINESE = ROOT / "README.zh-CN.md"
SERVER = ROOT / "src" / "origin_com_automation" / "server.py"
USER_GUIDE = ROOT / "docs" / "USER-GUIDE.md"
TOOL_REFERENCE = ROOT / "docs" / "TOOL-REFERENCE.md"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"
SECTION_MARKER = re.compile(r"<!-- section:([a-z0-9-]+) -->")
TOOL_NAME = re.compile(r'@strict_tool\(name="([a-z0-9_]+)"\)')
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CLICKABLE_BADGE = re.compile(
    r"\[!\[(?P<label>[^\]]+)\]\((?P<image>[^)]+)\)\]\((?P<target>[^)]+)\)"
)
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
HTML_ANCHOR = re.compile(
    r'<(?:a|span)\b[^>]*\b(?:id|name)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
MERMAID_BLOCK = re.compile(r"```mermaid\s*(.*?)```", re.IGNORECASE | re.DOTALL)
LIST_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+(.+)$", re.MULTILINE)
SUBHEADING = re.compile(r"^#{3,6}\s+(.+)$", re.MULTILINE)
EXPECTED_SECTIONS = [
    "what-it-does",
    "capabilities",
    "ask-codex",
    "examples",
    "installation",
    "defaults",
    "scope-limits",
    "troubleshooting",
    "architecture",
    "disclaimer",
    "references",
]
BADGE_PURPOSES = (
    ("version", r"\b(?:version|latest|stable)\b|\brelease\b(?!\s*gates?\b)"),
    ("release-gates", r"\b(?:release\s+gates?|gates?|actions|workflow|ci)\b"),
    ("windows", r"\bwindows\b"),
    ("python", r"\bpython\b"),
    ("origin-verified", r"\borigin\b"),
    ("codex-plugin", r"\bcodex\b"),
    ("mit-license", r"\b(?:mit|license)\b"),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, name: str) -> str:
    match = re.search(
        rf"<!--\s*section:{re.escape(name)}\s*-->(.*?)(?=<!--\s*section:|\Z)",
        text,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing README section marker: {name}"
    return match.group(1)


def _assert_request_template(text: str, patterns: tuple[str, ...]) -> None:
    items = LIST_ITEM.findall(_section(text, "ask-codex"))

    assert len(items) == 6
    for item, pattern in zip(items, patterns, strict=True):
        assert re.search(pattern, item, flags=re.IGNORECASE), item


def _assert_prompt_scenarios(text: str, patterns: tuple[str, ...]) -> None:
    headings = SUBHEADING.findall(_section(text, "examples"))

    assert len(headings) == 4
    for heading, pattern in zip(headings, patterns, strict=True):
        assert re.search(pattern, heading, flags=re.IGNORECASE), heading


def _badges_by_purpose(text: str) -> dict[str, re.Match[str]]:
    badges = list(CLICKABLE_BADGE.finditer(text))
    assert len(badges) == len(BADGE_PURPOSES)

    matches: dict[str, re.Match[str]] = {}
    for purpose, pattern in BADGE_PURPOSES:
        candidates = [
            badge
            for badge in badges
            if re.search(pattern, badge["label"], flags=re.IGNORECASE)
        ]
        assert len(candidates) == 1, f"expected one {purpose} badge, found {len(candidates)}"
        matches[purpose] = candidates[0]

    assert len({badge.start() for badge in matches.values()}) == len(BADGE_PURPOSES)
    return matches


def _document_anchors(text: str) -> set[str]:
    anchors = {anchor.casefold() for anchor in HTML_ANCHOR.findall(text)}
    for heading in MARKDOWN_HEADING.findall(text):
        label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        label = re.sub(r"[^\w\s-]", "", label.casefold())
        anchor = re.sub(r"[\s-]+", "-", label).strip("-")
        if anchor:
            anchors.add(anchor)
    return anchors


def _assert_badge_destinations(
    badges: dict[str, re.Match[str]], text: str, readme_name: str
) -> None:
    version_target = urlsplit(badges["version"]["target"])
    assert version_target.scheme.casefold() == "https"
    assert version_target.netloc.casefold() == "github.com"
    assert version_target.path.rstrip("/").casefold() == (
        "/sheldon12311815/origin-com-automation/releases/tag/v0.2.3"
    )

    gates_target = urlsplit(badges["release-gates"]["target"])
    assert gates_target.scheme.casefold() == "https"
    assert gates_target.netloc.casefold() == "github.com"
    assert gates_target.path.rstrip("/").casefold() == (
        "/sheldon12311815/origin-com-automation/actions/workflows/unit-tests.yml"
    )

    anchors = _document_anchors(text)
    local_badge_anchors = {
        "windows": "requirements",
        "python": "requirements",
        "codex-plugin": "installation",
    }
    for purpose, expected_anchor in local_badge_anchors.items():
        local_target = urlsplit(badges[purpose]["target"])
        assert local_target.scheme == ""
        assert local_target.netloc == ""
        assert local_target.path in {"", readme_name}
        assert local_target.fragment.casefold() == expected_anchor
        assert expected_anchor in anchors

    origin_target = urlsplit(badges["origin-verified"]["target"])
    assert origin_target.scheme == "" and origin_target.netloc == ""
    assert origin_target.path.removeprefix("./") == "docs/VALIDATION-0.2.3.md"

    license_target = urlsplit(badges["mit-license"]["target"])
    assert license_target.scheme == "" and license_target.netloc == ""
    assert license_target.path.removeprefix("./") == "LICENSE"


def test_readmes_have_the_same_ordered_public_sections():
    assert ENGLISH.is_file()
    assert CHINESE.is_file()

    english_sections = SECTION_MARKER.findall(_read(ENGLISH))
    chinese_sections = SECTION_MARKER.findall(_read(CHINESE))

    assert english_sections == EXPECTED_SECTIONS
    assert chinese_sections == EXPECTED_SECTIONS


def test_readmes_link_languages_show_the_logo_and_have_meaningful_badges():
    english = _read(ENGLISH)
    chinese = _read(CHINESE)

    assert "[简体中文](README.zh-CN.md)" in english
    assert "[English](README.md)" in chinese
    for readme_path, text in ((ENGLISH, english), (CHINESE, chinese)):
        assert "assets/origin-automation-logo.png" in text
        badges_by_purpose = _badges_by_purpose(text)
        badges = list(badges_by_purpose.values())
        assert all(match["label"].strip() for match in badges)
        assert all(match["image"].strip() for match in badges)
        assert all(match["target"].strip() not in {"", "#"} for match in badges)
        _assert_badge_destinations(badges_by_purpose, text, readme_path.name)


def test_readmes_include_a_six_field_request_template_and_four_prompt_scenarios():
    english = _read(ENGLISH)
    chinese = _read(CHINESE)

    _assert_request_template(
        english,
        (
            r"source",
            r"worksheet",
            r"\bX\b.*\bY\b|\bX/Y\b",
            r"range|branch",
            r"analysis|method",
            r"graph|output",
        ),
    )
    _assert_request_template(
        chinese,
        (
            r"源|数据",
            r"工作表",
            r"X.*Y",
            r"范围|分支",
            r"分析|方法",
            r"图|输出",
        ),
    )
    _assert_prompt_scenarios(
        english,
        (
            r"new data",
            r"existing.*OPJU",
            r"native.*fit",
            r"multi[- ]series.*plot",
        ),
    )
    _assert_prompt_scenarios(
        chinese,
        (
            r"新.*数据",
            r"现有.*OPJU",
            r"原生.*拟合|Origin.*拟合",
            r"多(?:系列|曲线).*(?:图|绘)",
        ),
    )


def test_readmes_document_marketplace_install_and_update_commands():
    commands = (
        "codex plugin marketplace add Sheldon12311815/origin-com-automation --ref marketplace",
        "codex plugin add origin-com-automation@origin-automation-marketplace",
        "codex plugin marketplace upgrade origin-automation-marketplace",
    )

    for text in (_read(ENGLISH), _read(CHINESE)):
        for command in commands:
            assert command in text


def test_readmes_document_the_same_editable_defaults_and_non_overwrite_behavior():
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

    english_defaults = _section(english, "defaults")
    chinese_defaults = _section(chinese, "defaults")
    assert re.search(
        r"non[- ]overwrite|(?:does?|will) not overwrite|never overwrite|without overwriting",
        english_defaults,
        flags=re.IGNORECASE,
    )
    assert re.search(r"不(?:会|要|得|应)?覆盖|禁止覆盖|另存", chinese_defaults)


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


def test_readmes_link_to_focused_user_tool_and_architecture_documents():
    references = (
        "docs/USER-GUIDE.md",
        "docs/TOOL-REFERENCE.md",
        "docs/ARCHITECTURE.md",
    )

    for text in (_read(ENGLISH), _read(CHINESE)):
        linked_targets = {
            target.split("#", 1)[0] for target in MARKDOWN_LINK.findall(text)
        }
        for reference in references:
            assert reference in linked_targets


def test_tool_reference_lists_every_public_mcp_tool():
    assert TOOL_REFERENCE.is_file()
    tool_names = TOOL_NAME.findall(_read(SERVER))
    reference = _read(TOOL_REFERENCE)

    assert len(tool_names) == 45
    missing = [name for name in tool_names if name not in reference]
    assert missing == []


def test_architecture_document_preserves_the_mermaid_nodes_and_flow():
    assert ARCHITECTURE.is_file()
    architecture = _read(ARCHITECTURE)
    mermaid_match = MERMAID_BLOCK.search(architecture)
    assert mermaid_match is not None
    mermaid = mermaid_match.group(1)

    node_ids = ("Codex", "MCP", "Controller", "STA", "Origin", "Artifacts")
    for node_id in node_ids:
        assert re.search(rf"\b{node_id}\b", mermaid)

    node_shape = r'(?:\s*(?:\[[^\]\n]*\]|\([^\)\n]*\)|\{[^\}\n]*\}))?'
    for source, target in (
        ("Codex", "MCP"),
        ("MCP", "Controller"),
        ("Controller", "STA"),
        ("STA", "Origin"),
        ("Origin", "Artifacts"),
        ("Artifacts", "Controller"),
        ("Controller", "Codex"),
    ):
        edge = re.compile(
            rf"^\s*{source}\b{node_shape}\s*-->\s*"
            rf"(?:\|[^|\n]*\|\s*)?{target}\b",
            re.MULTILINE,
        )
        assert edge.search(mermaid), f"missing Mermaid edge: {source} -> {target}"

    normalized = re.sub(r"[^a-z0-9]+", " ", architecture.casefold())
    for concepts in (
        ("json", "schema", "tool", "call"),
        ("serialized", "sta", "queue"),
        ("origin", "com", "labtalk", "x", "function"),
        ("verified", "artifact", "readback"),
    ):
        for concept in concepts:
            assert re.search(rf"\b{concept}\w*\b", normalized)


def test_user_guide_has_meaningful_usage_request_and_prompt_content():
    assert USER_GUIDE.is_file()
    guide = _read(USER_GUIDE)

    for tool_name in (
        "origin_import_data",
        "origin_open_project",
        "origin_run_analysis",
        "origin_create_graph",
        "origin_save_project",
        "origin_export_graph",
    ):
        assert tool_name in guide

    assert re.search(r"request template", guide, flags=re.IGNORECASE)
    request_patterns = (
        r"source",
        r"worksheet",
        r"\bX\b.*\bY\b|\bX/Y\b",
        r"range|branch",
        r"analysis|method",
        r"graph|output",
    )
    list_items = LIST_ITEM.findall(guide)
    assert any(
        all(
            re.search(pattern, item, flags=re.IGNORECASE)
            for item, pattern in zip(
                list_items[start : start + len(request_patterns)],
                request_patterns,
                strict=True,
            )
        )
        for start in range(len(list_items) - len(request_patterns) + 1)
    )

    assert re.search(r"(?:ready-to-use|example) prompts?", guide, flags=re.IGNORECASE)
    prompt_headings = SUBHEADING.findall(guide)
    for scenario in (
        r"new data",
        r"existing.*OPJU",
        r"native.*fit",
        r"multi[- ]series.*plot",
    ):
        assert any(
            re.search(scenario, heading, flags=re.IGNORECASE)
            for heading in prompt_headings
        )


def test_readme_local_links_resolve_to_repository_files():
    for readme in (ENGLISH, CHINESE):
        text = _read(readme)
        targets = MARKDOWN_LINK.findall(text)
        targets.extend(match["target"] for match in CLICKABLE_BADGE.finditer(text))
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
