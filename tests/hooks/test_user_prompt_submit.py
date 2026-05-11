import io
import json
from unittest.mock import patch

from hooks.user_prompt_submit import main


def test_emits_additional_context_block_from_packet(monkeypatch, capsys):
    event = {"prompt": "How does auth work?", "session_id": "s1"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")

    fake_packet = {"rendered": "## Facts\n- Auth uses OIDC.\n",
                   "context_quality": "strong"}
    with patch("hooks.user_prompt_submit._fetch_packet", return_value=fake_packet), \
         patch("hooks.user_prompt_submit.enqueue", return_value={"observation_id": "id"}):
        rc = main()

    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "Auth uses OIDC" in payload["hookSpecificOutput"]["additionalContext"]
