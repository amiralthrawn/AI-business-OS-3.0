import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.entities.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class Repository(Generic[ModelType]):
    """Generic CRUD access shared by every Data Core entity. Domain-specific
    repositories can subclass this when they need custom queries."""

    def __init__(self, session: Session, model: type[ModelType]) -> None:
        self.session = session
        self.model = model

    def get(self, id_: uuid.UUID) -> ModelType | None:
        return self.session.get(self.model, id_)

    def list(self) -> list[ModelType]:
        return list(self.session.scalars(select(self.model)))

    def add(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        return entity
