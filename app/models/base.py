from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC now. Avoids deprecated datetime.utcnow."""
    return datetime.now(UTC)


class TimestampMixin(SQLModel):
    """Adds created_at and updated_at to a model.

    `updated_at` is touched in service-layer update methods, not via DB triggers,
    to keep the schema portable across SQLite/Postgres.
    """

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
