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
CLICKABLE_BADGE = re.compile(
    r"\[!\[(?P<label>[^\]]+)\]\((?P<image>[^)]+)\)\]\((?P<target>[^)]+)\)"
)
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
    for text in (english, chinese):
        assert "assets/origin-automation-logo.png" in text
        badges = list(CLICKABLE_BADGE.finditer(text))
        assert len(badges) == 7
        assert all(match["label"].strip() for match in badges)
        assert all(match["image"].strip() for match in badges)
        assert all(match["target"].strip() not in {"", "#"} for match in badges)

        for purpose in (
            r"release",
            r"gate|actions",
            r"windows",
            r"python",
            r"origin",
            r"codex",
            r"license|mit",
        ):
            assert any(
                re.search(
                    purpose,
                    " ".join(match[group] for group in ("label", "image", "target")),
                    flags=re.IGNORECASE,
                )
                for match in badges
            )


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


def test_readmes_list_every_public_mcp_tool():
    tool_names = TOOL_NAME.findall(_read(SERVER))

    assert len(tool_names) == 45
    for text in (_read(ENGLISH), _read(CHINESE)):
        missing = [name for name in tool_names if name not in text]
        assert missing == []


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
