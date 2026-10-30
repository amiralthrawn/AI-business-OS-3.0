import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.entities import Customer
from app.core.events.bus import EventBus


class ReadCustomerInput(BaseModel):
    customer_id: uuid.UUID


class ReadCustomerOutput(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None


def _execute(session: Session, _event_bus: EventBus | None, data: ReadCustomerInput) -> ReadCustomerOutput:
    customer = session.get(Customer, data.customer_id)
    if customer is None:
        raise CapabilityExecutionError(f"Customer {data.customer_id} not found")

    return ReadCustomerOutput(id=customer.id, name=customer.name, country=customer.country)


read_customer_capability = Capability(
    name="read_customer",
    description="Reads a Customer's core attributes from the Data Core.",
    input_schema=ReadCustomerInput,
    output_schema=ReadCustomerOutput,
    requires_human_validation=False,
    executor=_execute,
)
