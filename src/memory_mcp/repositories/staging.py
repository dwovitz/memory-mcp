from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from memory_mcp.models import StagingObservation


class StagingRepository:
    """Postgres-backed FIFO queue for raw session observations."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def enqueue(self, source: str, payload: dict, scope: dict) -> uuid.UUID:
        obs = StagingObservation(source=source, payload=payload, scope=scope)
        self._s.add(obs)
        self._s.flush()
        return obs.id

    def peek_pending(self, *, limit: int = 50) -> Sequence[StagingObservation]:
        stmt = (
            select(StagingObservation)
            .where(StagingObservation.status == "pending")
            .order_by(StagingObservation.created_at)
            .limit(limit)
        )
        return self._s.execute(stmt).scalars().all()

    def claim_batch(self, *, limit: int, worker_id: str) -> Sequence[StagingObservation]:
        # SELECT ... FOR UPDATE SKIP LOCKED: multiple workers claim disjoint batches
        # without coordination — the standard Postgres distributed-queue primitive.
        stmt = (
            select(StagingObservation.id)
            .where(StagingObservation.status == "pending")
            .order_by(StagingObservation.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        ids = list(self._s.execute(stmt).scalars().all())
        if not ids:
            return []
        now = datetime.now(timezone.utc)
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id.in_(ids))
            .values(status="claimed", claimed_at=now)
            .execution_options(synchronize_session=False)
        )
        self._s.flush()
        # Expire cached objects so subsequent selects reload from DB
        self._s.expire_all()
        return self._s.execute(
            select(StagingObservation).where(StagingObservation.id.in_(ids))
        ).scalars().all()

    def mark_done(self, obs_id: uuid.UUID) -> None:
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id == obs_id)
            .values(status="done", completed_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session=False)
        )

    def mark_failed(self, obs_id: uuid.UUID, error: str) -> None:
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id == obs_id)
            .values(
                status="failed",
                error_message=error,
                attempts=StagingObservation.attempts + 1,
                completed_at=datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
