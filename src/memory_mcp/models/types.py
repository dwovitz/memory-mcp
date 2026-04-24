"""Custom database column types."""

from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """PostgreSQL pgvector column type placeholder."""

    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "vector"
