import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability
from app.core.entities import Transaction
from app.core.events.bus import EventBus


class ReadTransactionsInput(BaseModel):
    supplier_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    limit: int = 10

    @model_validator(mode="after")
    def _require_at_least_one_filter(self) -> "ReadTransactionsInput":
        if self.supplier_id is None and self.product_id is None and self.customer_id is None:
            raise ValueError("read_transactions requires a supplier_id, a product_id or a customer_id")
        return self


class TransactionSummary(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    amount: float
    currency: str
    occurred_at: datetime


class ReadTransactionsOutput(BaseModel):
    transactions: list[TransactionSummary]


def _execute(session: Session, _event_bus: EventBus | None, data: ReadTransactionsInput) -> ReadTransactionsOutput:
    query = session.query(Transaction)
    if data.supplier_id is not None:
        query = query.filter(Transaction.supplier_id == data.supplier_id)
    if data.product_id is not None:
        query = query.filter(Transaction.product_id == data.product_id)
    if data.customer_id is not None:
        query = query.filter(Transaction.customer_id == data.customer_id)

    rows = query.order_by(Transaction.occurred_at.desc()).limit(data.limit).all()

    return ReadTransactionsOutput(
        transactions=[
            TransactionSummary(
                id=t.id,
                type=t.type.value,
                status=t.status.value,
                amount=t.amount,
                currency=t.currency,
                occurred_at=t.occurred_at,
            )
            for t in rows
        ]
    )


read_transactions_capability = Capability(
    name="read_transactions",
    description="Reads recent Transactions for a Supplier, a Product or a Customer from the Data Core.",
    input_schema=ReadTransactionsInput,
    output_schema=ReadTransactionsOutput,
    requires_human_validation=False,
    executor=_execute,
)
