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

