from pathlib import Path


def test_origin_skill_has_trigger_metadata_and_safe_workflow():
    skill = Path(__file__).parents[2] / "skills" / "origin-automation" / "SKILL.md"

    text = skill.read_text(encoding="utf-8")

    assert "name: origin-automation" in text
    assert "description: Use when" in text
    assert "origin_health_check" in text
    assert "origin_start" in text
    assert "working copy" in text.lower()
    assert "attached" in text.lower()
    assert "origin_shutdown" in text
    assert "data_format=auto" in text
    assert "result_string_variables" in text
    assert "label_column" in text
    assert "categorical_style" in text
    assert "origin_save_and_replace_source" in text
    assert "expected_source_sha256" in text
    assert "## Task Routing" in text
    assert "## Fast Critical Path" in text
    assert "## Call Budget" in text
    assert "one targeted correction" in text
    assert "one initial `origin_list_objects`" in text
    assert "second `origin_list_objects`" in text
    assert "Do not narrate every MCP call" in text
    assert "same failure repeats" in text
    assert "origin_recover_session" in text
    assert "target_mode=\"new_workbook\"" in text
    assert "column_profiles" in text
    assert "system installation template" in text
    assert "Do not call `origin_shutdown` first" in text
    assert 'source_mode="linked"' in text
    assert 'source_mode="snapshot"' in text
    assert "origin_set_column_formula" in text
    assert "F(x)" in text
    assert 'backend="origin_native"' in text
    assert 'backend="python"' in text
    assert "Never silently fall back" in text
