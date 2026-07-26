from origin_com_automation.knowledge import query_knowledge


def test_knowledge_query_filters_domain_status_and_term():
    results = query_knowledge(term="op_change", domain="analysis", status="verified")
    assert results
    assert all(item["domain"] == "analysis" for item in results)
    assert all(item["status"] == "verified" for item in results)
    assert all(item["official_url"].startswith("https://") for item in results)


def test_knowledge_query_is_bounded_and_contains_tool_mapping():
    results = query_knowledge(term="Origin", limit=3)
    assert len(results) <= 3
    assert all("tools" in item for item in results)


def test_knowledge_covers_linked_import_and_origin_column_formulas():
    formulas = query_knowledge(term="csetvalue", status="verified")
    connectors = query_knowledge(term="linked import", status="verified")

    assert formulas
    assert "origin_set_column_formula" in formulas[0]["tools"]
    assert any("origin_import_data" in item["tools"] for item in connectors)
