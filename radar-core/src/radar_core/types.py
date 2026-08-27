from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.engine import Dialect


class UTCDateTime(TypeDecorator[datetime]):
    """DateTime type that ensures UTC timezone is preserved across a SQLite round-trip.

    Naive datetimes passed on bind are assumed to already represent UTC and are stored
    as-is; callers should always construct values via `datetime.now(UTC)`.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None:
            if value.tzinfo is not None:
                # Convert to UTC if timezone-aware
                return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None:
            # Add UTC timezone when retrieving from database
            return value.replace(tzinfo=UTC)
        return value
