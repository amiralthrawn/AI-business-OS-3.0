from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.events.bus import EventBus


class CapabilityError(Exception):
    """Base class for all Capability-related errors."""


class CapabilityNotFoundError(CapabilityError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown capability: '{name}'")
        self.name = name


class CapabilityExecutionError(CapabilityError):
    """Raised by a capability's executor for an expected failure (e.g. the
    requested entity doesn't exist) -- distinct from an unexpected bug, and
    always safe to surface as a clean, user-facing error message."""


@dataclass(frozen=True)
class Capability:
    """A named, reusable unit of read or action the AI layer can invoke. Every
    capability declares its own input/output shape, whether it reads or acts
    (`kind`), and whether invoking it requires human validation before any
    side effect takes place.

    `requires_human_validation=True` is a declaration, not an enforcement
    mechanism by itself: the actual guarantee that nothing executes
    automatically lives in the domain service a capability delegates to (see
    create_task.py -> ActionsService.create_task, which has no parameter to
    set any status other than PENDING_VALIDATION).
    """

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    requires_human_validation: bool
    executor: Callable[[Session, EventBus | None, BaseModel], BaseModel]
    kind: Literal["read", "action"] = "read"

    def run(self, session: Session, event_bus: EventBus | None = None, **kwargs: Any) -> BaseModel:
        validated_input = self.input_schema(**kwargs)
        result = self.executor(session, event_bus, validated_input)
        if not isinstance(result, self.output_schema):
            raise TypeError(f"Capability '{self.name}' executor must return {self.output_schema.__name__}")
        return result
