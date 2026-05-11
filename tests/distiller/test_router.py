from memory_mcp.distiller.router import ModelChoice, select_model


def test_tool_only_simple_routes_to_haiku():
    batch = [
        {"source": "post_tool_use", "payload": {"tool": "Read"}},
        {"source": "post_tool_use", "payload": {"tool": "Glob"}},
    ]
    assert select_model(batch) is ModelChoice.HAIKU


def test_mixed_with_user_prompt_routes_to_sonnet():
    batch = [
        {"source": "user_prompt_submit", "payload": {"text": "design auth"}},
        {"source": "post_tool_use", "payload": {"tool": "Edit"}},
    ]
    assert select_model(batch) is ModelChoice.SONNET


def test_large_payload_routes_to_sonnet():
    batch = [
        {"source": "post_tool_use",
         "payload": {"tool": "Edit", "diff": "x" * 20_000}},
    ]
    assert select_model(batch) is ModelChoice.SONNET
