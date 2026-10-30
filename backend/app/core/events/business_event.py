import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BusinessEvent(BaseModel):
    """An immutable record of something that happened in the business, published
    on the Event Bus. `correlation_id` ties together an originating event and
    whatever events it causes downstream (e.g. a Risk created in reaction to a
    supplier cost increase shares the same correlation_id)."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime = Field(default_factory=_utcnow)
