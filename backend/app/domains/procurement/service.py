import uuid

from sqlalchemy.orm import Session

from app.core.analytics import compute_company_financials, compute_monthly_series
from app.core.entities import Product, TransactionType
from app.core.events.business_event import BusinessEvent
from app.core.events.bus import EventBus
from app.data.service import list_suppliers, list_transactions
from app.home.service import HomeService

SUPPLIER_COST_INCREASED = "SupplierCostIncreased"

_EMPTY_OVERVIEW: dict = {
    "supplier_count": 0,
    "total_spend": 0.0,
    "suppliers": [],
    "intelligence": [],
    "recent_transactions": [],
    "monthly_purchases": [],
}


def get_procurement_overview(session: Session, company_id: uuid.UUID | None) -> dict:
    """Procurement domain overview (Step 23B): composed entirely from
    `app.data.service.list_suppliers` (already used by the Suppliers data
    page), `compute_company_financials` (its total_costs IS total spend),
    and `HomeService.get_ai_priorities` filtered to the "procurement"
    domain. No new source of truth."""

    if company_id is None:
        return dict(_EMPTY_OVERVIEW)

    suppliers = list_suppliers(session, company_id)
    financials = compute_company_financials(session, company_id)
    intelligence = [
        s for s in HomeService(session).get_ai_priorities(company_id, limit=1000) if s["domain"] == "procurement"
    ]
    recent_transactions = [t for t in list_transactions(session, company_id, limit=50) if t["supplier_id"] is not None][:10]
    # Same cost basis as compute_company_financials.total_costs (Purchase Orders + Invoices).
    monthly_purchases = compute_monthly_series(session, company_id, [TransactionType.PURCHASE_ORDER, TransactionType.INVOICE])

    return {
        "supplier_count": len(suppliers),
        "total_spend": financials.total_costs,
        "suppliers": suppliers,
        "intelligence": intelligence,
        "recent_transactions": recent_transactions,
        "monthly_purchases": monthly_purchases,
    }


class ProcurementError(Exception):
    """Raised when a Procurement operation cannot be carried out as requested."""


class ProcurementService:
    """Minimal Procurement operations over the shared Data Core. Holds no data of
    its own: it reads and writes the existing Supplier/Product entities and
    publishes Business Events for whatever downstream layers will react to."""

    def __init__(self, session: Session, event_bus: EventBus) -> None:
        self.session = session
        self.event_bus = event_bus

    def record_supplier_cost_increase(
        self, supplier_id: uuid.UUID, product_id: uuid.UUID, new_unit_cost: float
    ) -> BusinessEvent:
        product = self.session.get(Product, product_id)
        if product is None or product.supplier_id != supplier_id:
            raise ProcurementError(f"Product {product_id} not found for supplier {supplier_id}")

        old_unit_cost = product.unit_cost
        if old_unit_cost is None or old_unit_cost <= 0:
            raise ProcurementError(f"Product {product_id} has no valid current unit cost to compare against")
        if new_unit_cost <= old_unit_cost:
            raise ProcurementError("new_unit_cost must be strictly higher than the current unit cost")

        variation_pct = (new_unit_cost - old_unit_cost) / old_unit_cost

        product.unit_cost = new_unit_cost
        self.session.add(product)
        self.session.commit()

        event = BusinessEvent(
            event_type=SUPPLIER_COST_INCREASED,
            source="procurement",
            payload={
                "supplier_id": str(supplier_id),
                "product_id": str(product_id),
                "old_unit_cost": old_unit_cost,
                "new_unit_cost": new_unit_cost,
                "variation_pct": variation_pct,
            },
        )
        self.event_bus.publish(event)
        return event
