import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
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
    ingest_key = f"distill:auth-oidc-{uuid4()}"
    with session_scope() as s:
        observation_id = StagingRepository(s).enqueue(
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
        "observation_ids": [str(observation_id)],
        "ingest_key": ingest_key,
    }])
    svc = DistillerService(client=fake, worker_id="test-w")
    processed = svc.distill_once(batch_size=10)

    assert processed >= 1
    with session_scope() as s:
        match = MemoryService(session=s).memories.find_active_by_metadata_key(
            "ingest_key", ingest_key
        )
        assert match is not None
        assert "OIDC" in match.content
        assert match.metadata_["source"] == "auto_capture"
        assert match.metadata_["observation_sources"] == ["post_tool_use"]
        assert match.metadata_["observation_ids"] == [str(observation_id)]
        assert match.sensitivity == "private"


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


def test_distill_once_rejects_invalid_output_without_partial_promotion() -> None:
    valid_key = f"distill:valid-{uuid4()}"
    with session_scope() as s:
        observation_id = StagingRepository(s).enqueue(
            "post_tool_use", {"tool": "Edit"}, {"project": "memory-mcp"}
        )
        s.commit()

    valid_entry = {
        "memory_type": "project_fact",
        "content": "The project uses Postgres.",
        "confidence": 0.8,
        "tags": ["postgres"],
        "applies_to": {"project": "memory-mcp"},
        "observation_ids": [str(observation_id)],
        "ingest_key": valid_key,
    }
    fake = _FakeClient([valid_entry, {**valid_entry, "observation_ids": ["outside-batch"]}])

    DistillerService(client=fake, worker_id="test-w").distill_once()

    with session_scope() as s:
        assert s.get(StagingObservation, observation_id).status == "failed"
        assert MemoryService(session=s).memories.find_active_by_metadata_key(
            "ingest_key", valid_key
        ) is None


def test_normalize_assigns_claim_accurate_private_provenance() -> None:
    normalized = DistillerService._normalize(
        {
            "memory_type": "project_fact",
            "content": "The project uses Postgres.",
            "confidence": 0.8,
            "tags": ["postgres"],
            "applies_to": {"project": "memory-mcp"},
            "observation_ids": ["obs-2"],
            "ingest_key": "distill:postgres",
        },
        claimed_observations={
            "obs-1": {"source": "post_tool_use", "scope": {"project": "memory-mcp"}},
            "obs-2": {"source": "session_end", "scope": {"project": "memory-mcp"}},
        },
    )

    assert normalized["metadata"]["source"] == "auto_capture"
    assert normalized["metadata"]["observation_ids"] == ["obs-2"]
    assert normalized["metadata"]["observation_sources"] == ["session_end"]
    assert normalized["sensitivity"] == "private"


def test_normalize_rejects_invalid_model_output() -> None:
    entry = {
        "memory_type": "project_fact",
        "content": "The project uses Postgres.",
        "confidence": 1.0,
        "tags": [],
        "applies_to": {"project": "memory-mcp"},
        "observation_ids": ["obs-1"],
        "ingest_key": "distill:bad",
    }
    claimed_observations = {
        "obs-1": {"source": "session_end", "scope": {"project": "memory-mcp"}}
    }

    with pytest.raises(ValueError, match="unsupported memory_type"):
        DistillerService._normalize(
            {**entry, "memory_type": "unknown"}, claimed_observations=claimed_observations
        )
    with pytest.raises(ValueError, match="secret or credential"):
        DistillerService._normalize(
            {**entry, "content": "Bearer " + "x" * 24},
            claimed_observations=claimed_observations,
        )
    with pytest.raises(ValueError, match="subset of claimed"):
        DistillerService._normalize(
            {**entry, "observation_ids": ["outside-batch"]},
            claimed_observations=claimed_observations,
        )
    with pytest.raises(ValueError, match="exactly match"):
        DistillerService._normalize(
            {**entry, "applies_to": {}},
            claimed_observations=claimed_observations,
        )
