import pytest

from memory_mcp.db import session_scope
from memory_mcp.models import StagingObservation
from memory_mcp.repositories.staging import StagingRepository
from sqlalchemy import delete


@pytest.fixture(autouse=True)
def clean_staging():
    """Truncate staging_observations before each test for isolation."""
    with session_scope() as s:
        s.execute(delete(StagingObservation))
        s.commit()
    yield
    with session_scope() as s:
        s.execute(delete(StagingObservation))
        s.commit()


def test_enqueue_returns_id_and_pending():
    with session_scope() as s:
        repo = StagingRepository(s)
        obs_id = repo.enqueue(
            source="post_tool_use",
            payload={"tool": "Read"},
            scope={"workspace": "ai", "project": "memory-mcp"},
        )
        s.flush()
        rows = repo.peek_pending(limit=10)
        assert any(r.id == obs_id and r.status == "pending" for r in rows)


def test_claim_batch_marks_claimed_and_skips_already_claimed():
    with session_scope() as s:
        repo = StagingRepository(s)
        ids = [
            repo.enqueue("post_tool_use", {"i": i}, {"project": "memory-mcp"})
            for i in range(3)
        ]
        s.commit()
        first = repo.claim_batch(limit=2, worker_id="w1")
        assert len(first) == 2
        assert all(r.status == "claimed" for r in first)
        second = repo.claim_batch(limit=10, worker_id="w2")
        assert len(second) == 1
        assert second[0].id == ids[2]


def test_mark_done_and_failed():
    with session_scope() as s:
        repo = StagingRepository(s)
        obs_id = repo.enqueue("post_tool_use", {}, {"project": "memory-mcp"})
        s.commit()
        claimed = repo.claim_batch(limit=1, worker_id="w1")
        repo.mark_done(claimed[0].id)
        s.commit()

        obs_id2 = repo.enqueue("post_tool_use", {}, {"project": "memory-mcp"})
        s.commit()
        claimed2 = repo.claim_batch(limit=1, worker_id="w1")
        repo.mark_failed(claimed2[0].id, "boom")
        s.commit()

        assert s.get(type(claimed[0]), obs_id).status == "done"
        failed = s.get(type(claimed[0]), obs_id2)
        assert failed.status == "failed"
        assert failed.error_message == "boom"
        assert failed.attempts == 1
