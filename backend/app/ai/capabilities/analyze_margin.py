import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.capabilities.base import Capability, CapabilityExecutionError
from app.core.entities import Product, Transaction, TransactionType
from app.core.events.bus import EventBus


class AnalyzeMarginInput(BaseModel):
    product_id: uuid.UUID


class AnalyzeMarginOutput(BaseModel):
    product_id: uuid.UUID
    cost: float
    revenue: float | None
    margin: float | None
    margin_percentage: float | None
    limitation: str | None


def _execute(session: Session, _event_bus: EventBus | None, data: AnalyzeMarginInput) -> AnalyzeMarginOutput:
    """Deterministic arithmetic only -- no LLM involved. The Data Core's seed
    data only contains purchase_order transactions (cost side); no sales_order
    transactions exist yet to represent revenue. When that's the case, this
    returns the aggregate cost that IS available and an explicit `limitation`
    instead of fabricating a margin from data that doesn't exist."""

    product = session.get(Product, data.product_id)
    if product is None:
        raise CapabilityExecutionError(f"Product {data.product_id} not found")

    cost_transactions = (
        session.query(Transaction)
        .filter(
            Transaction.product_id == data.product_id,
            Transaction.type.in_([TransactionType.PURCHASE_ORDER, TransactionType.INVOICE]),
        )
        .all()
    )
    revenue_transactions = (
        session.query(Transaction)
        .filter(Transaction.product_id == data.product_id, Transaction.type == TransactionType.SALES_ORDER)
        .all()
    )

    cost = sum(t.amount for t in cost_transactions)

    if not revenue_transactions:
        return AnalyzeMarginOutput(
            product_id=product.id,
            cost=cost,
            revenue=None,
            margin=None,
            margin_percentage=None,
            limitation=(
                "No sales_order transactions exist for this product in the Data Core, "
                "so revenue and margin cannot be computed. Only aggregate purchase cost is available."
            ),
        )

    revenue = sum(t.amount for t in revenue_transactions)
    margin = revenue - cost
    margin_percentage = margin / revenue if revenue else None

    return AnalyzeMarginOutput(
        product_id=product.id,
        cost=cost,
        revenue=revenue,
        margin=margin,
        margin_percentage=margin_percentage,
        limitation=None,
    )


analyze_margin_capability = Capability(
    name="analyze_margin",
    description="Computes cost/revenue/margin for a Product from existing Transactions only.",
    input_schema=AnalyzeMarginInput,
    output_schema=AnalyzeMarginOutput,
    requires_human_validation=False,
    executor=_execute,
)
