import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BusinessContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    company_size: str | None
    country: str | None
    business_model: str | None
    monitored_domains: list[str]
    home_focus: list[str]
    notification_level: str
    stated_objectives: str | None
    declared_baselines: dict[str, float]
    learned_notes: list[str]
    created_at: datetime
    updated_at: datetime


class BusinessContextUpdate(BaseModel):
    company_size: str | None = None
    country: str | None = None
    business_model: str | None = None
    monitored_domains: list[str] | None = None
    home_focus: list[str] | None = None
    notification_level: str | None = None
    stated_objectives: str | None = None
    declared_baselines: dict[str, float] | None = None


class ConfigurationSuggestionRead(BaseModel):
    field: str
    current_value: object
    suggested_value: object
    reason: str
    evidence_count: int
