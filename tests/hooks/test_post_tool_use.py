import io
import json
from unittest.mock import patch

from hooks.post_tool_use import main
from hooks.post_tool_use import _truncate_json


def test_main_reads_stdin_event_and_enqueues(monkeypatch):
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/x.py"},
        "tool_response": {"success": True},
        "cwd": "/repo/memory-mcp",
        "session_id": "abc123",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setenv("MEMORY_MCP_WORKSPACE", "ai")
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")

    with patch("hooks.post_tool_use.enqueue") as enq:
        enq.return_value = {"observation_id": "id1"}
        rc = main()
    assert rc == 0
    enq.assert_called_once()
    kwargs = enq.call_args.kwargs
    assert kwargs["source"] == "post_tool_use"
    assert kwargs["payload"]["tool"] == "Edit"
    assert kwargs["scope"]["project"] == "memory-mcp"


def test_truncate_json_bounds_large_tool_input() -> None:
    result = _truncate_json({"contents": "x" * 5000})

    assert isinstance(result, str)
    assert result.endswith("...<truncated>")
    assert len(result) < 4_100
