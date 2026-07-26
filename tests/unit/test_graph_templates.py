import hashlib

import pytest

from origin_com_automation.graphs.templates import GraphTemplateError, apply_template_plan, discover_templates


def test_template_discovery_is_bounded_to_explicit_roots(tmp_path):
    root = tmp_path / "templates"
    root.mkdir()
    template = root / "journal.otpu"
    template.write_bytes(b"template")
    (root / "ignored.txt").write_text("x", encoding="utf-8")
    discovered = discover_templates([str(root)])
    assert len(discovered) == 1
    assert discovered[0]["path"] == str(template.resolve())
    assert discovered[0]["sha256"] == hashlib.sha256(b"template").hexdigest()


def test_template_application_requires_matching_digest_and_layer_count(tmp_path):
    template = tmp_path / "journal.otpu"
    template.write_bytes(b"template")
    digest = hashlib.sha256(b"template").hexdigest()
    plan = apply_template_plan(
        graph_ref="Graph1",
        template_path=str(template),
        expected_sha256=digest,
        required_layers=2,
        actual_layers=2,
    )
    assert plan.template_path == template.resolve()
    with pytest.raises(GraphTemplateError, match="SHA-256"):
        apply_template_plan(
            graph_ref="Graph1", template_path=str(template), expected_sha256="0" * 64
        )
    with pytest.raises(GraphTemplateError, match="layer count"):
        apply_template_plan(
            graph_ref="Graph1",
            template_path=str(template),
            expected_sha256=digest,
            required_layers=2,
            actual_layers=1,
        )

