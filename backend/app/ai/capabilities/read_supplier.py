import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.entities import Supplier
from app.core.events.bus import EventBus


class ReadSupplierInput(BaseModel):
    supplier_id: uuid.UUID


class ReadSupplierOutput(BaseModel):
    id: uuid.UUID
    name: str
    country: str | None
    product_count: int


def _execute(session: Session, _event_bus: EventBus | None, data: ReadSupplierInput) -> ReadSupplierOutput:
    supplier = session.get(Supplier, data.supplier_id)
    if supplier is None:
        raise CapabilityExecutionError(f"Supplier {data.supplier_id} not found")

    return ReadSupplierOutput(
        id=supplier.id,
        name=supplier.name,
        country=supplier.country,
        product_count=len(supplier.products),
    )


read_supplier_capability = Capability(
    name="read_supplier",
    description="Reads a Supplier's core attributes from the Data Core.",
    input_schema=ReadSupplierInput,
    output_schema=ReadSupplierOutput,
    requires_human_validation=False,
    executor=_execute,
)
