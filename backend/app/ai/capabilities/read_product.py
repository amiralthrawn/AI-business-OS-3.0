import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.entities import Product
from app.core.events.bus import EventBus


class ReadProductInput(BaseModel):
    product_id: uuid.UUID


class ReadProductOutput(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None
    unit_cost: float | None
    supplier_id: uuid.UUID | None


def _execute(session: Session, _event_bus: EventBus | None, data: ReadProductInput) -> ReadProductOutput:
    product = session.get(Product, data.product_id)
    if product is None:
        raise CapabilityExecutionError(f"Product {data.product_id} not found")

    return ReadProductOutput(
        id=product.id,
        name=product.name,
        sku=product.sku,
        unit_cost=product.unit_cost,
        supplier_id=product.supplier_id,
    )


read_product_capability = Capability(
    name="read_product",
    description="Reads a Product's core attributes from the Data Core.",
    input_schema=ReadProductInput,
    output_schema=ReadProductOutput,
    requires_human_validation=False,
    executor=_execute,
)
