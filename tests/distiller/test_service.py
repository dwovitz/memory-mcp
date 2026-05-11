import json
from unittest.mock import MagicMock

from memory_mcp.db import session_scope
from memory_mcp.distiller.service import DistillerService
from memory_mcp.models import StagingObservation
from memory_mcp.repositories.staging import StagingRepository
from memory_mcp.services.memory_service import MemoryService
from sqlalchemy import select


class _FakeClient:
    def __init__(self, response_json: list[dict]):
        self._response = response_json
        self.calls = []

    @property
    def messages(self):
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return MagicMock(content=[MagicMock(text=json.dumps(outer._response))])

        return _Messages()


def test_distill_once_promotes_durable_memories():
    with session_scope() as s:
        StagingRepository(s).enqueue(
            "post_tool_use",
            {"tool": "Edit", "file": "src/auth.py", "decision": "use OIDC"},
            {"workspace": "ai", "project": "memory-mcp"},
        )
        s.commit()

    fake = _FakeClient([{
        "memory_type": "architecture_decision",
        "content": "Auth uses OIDC for memory-mcp.",
        "confidence": 0.9,
        "tags": ["auth", "oidc"],
        "applies_to": {"workspace": "ai", "project": "memory-mcp"},
        "ingest_key": "distill:auth-oidc-1",
    }])
    svc = DistillerService(client=fake, worker_id="test-w")
    processed = svc.distill_once(batch_size=10)

    assert processed >= 1
    with session_scope() as s:
        match = MemoryService(session=s).memories.find_active_by_metadata_key(
            "ingest_key", "distill:auth-oidc-1"
        )
        assert match is not None
        assert "OIDC" in match.content


def test_distill_once_marks_failed_on_invalid_json():
    with session_scope() as s:
        StagingRepository(s).enqueue(
            "post_tool_use", {"tool": "Edit"}, {"project": "memory-mcp"})
        s.commit()

    fake = MagicMock()
    fake.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
    svc = DistillerService(client=fake, worker_id="test-w")
    svc.distill_once(batch_size=10)

    with session_scope() as s:
        rows = s.execute(select(StagingObservation)).scalars().all()
        assert any(r.status == "failed" for r in rows)
