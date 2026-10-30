import uuid

from pydantic import BaseModel, ConfigDict


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    industry: str | None


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
