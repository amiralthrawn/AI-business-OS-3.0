import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability
from app.core.events.bus import EventBus
from app.home.service import HomeService


class ListPrioritiesInput(BaseModel):
    limit: int = 10


class PriorityItemOutput(BaseModel):
    kind: str
    id: uuid.UUID
    title: str
    description: str | None
    severity: str | None
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None


class ListPrioritiesOutput(BaseModel):
    priorities: list[PriorityItemOutput]
    total_open_risks: int
    total_open_opportunities: int
    pending_validation_tasks: int


def _execute(session: Session, _event_bus: EventBus | None, data: ListPrioritiesInput) -> ListPrioritiesOutput:
    # Reuses HomeService rather than querying directly: "what deserves
    # attention" must mean the same thing here as it does on the Home page.
    home = HomeService(session)
    priorities = home.get_priorities(limit=data.limit)
    risks_summary = home.get_risks_summary()
    opportunities_summary = home.get_opportunities_summary()
    tasks_summary = home.get_tasks_summary()

    return ListPrioritiesOutput(
        priorities=[
            PriorityItemOutput(
                kind=item["kind"],
                id=item["id"],
                title=item["title"],
                description=item["description"],
                severity=item["severity"],
                related_entity_type=item["related_entity_type"].value if item["related_entity_type"] else None,
                related_entity_id=item["related_entity_id"],
            )
            for item in priorities
        ],
        total_open_risks=risks_summary["total_risks"],
        total_open_opportunities=opportunities_summary["total_opportunities"],
        pending_validation_tasks=tasks_summary["pending_validation_tasks"],
    )


list_priorities_capability = Capability(
    name="list_priorities",
    description="Lists open Risks and Opportunities ranked by severity/impact, plus pending Task count.",
    input_schema=ListPrioritiesInput,
    output_schema=ListPrioritiesOutput,
    requires_human_validation=False,
    executor=_execute,
)
