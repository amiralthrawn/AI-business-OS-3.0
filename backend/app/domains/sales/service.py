"""Sales domain overview (Step 23B): composed entirely from
`app.data.service.list_customers` (already used by the Customers data page),
`compute_company_financials` for total revenue, and
`HomeService.get_ai_priorities` filtered to the "sales" domain. No CRM
pipeline, no Deal entity, no new source of truth.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.analytics import compute_company_financials, compute_monthly_series
from app.core.entities import TransactionType
from app.data.service import list_customers, list_transactions
from app.home.service import HomeService

_EMPTY_OVERVIEW: dict = {
    "customer_count": 0,
    "total_revenue": 0.0,
    "customers": [],
    "intelligence": [],
    "recent_transactions": [],
    "monthly_sales": [],
}


def get_sales_overview(session: Session, company_id: uuid.UUID | None) -> dict:
    if company_id is None:
        return dict(_EMPTY_OVERVIEW)

    customers = list_customers(session, company_id)
    financials = compute_company_financials(session, company_id)
    intelligence = [
        s for s in HomeService(session).get_ai_priorities(company_id, limit=1000) if s["domain"] == "sales"
    ]
    recent_transactions = [t for t in list_transactions(session, company_id, limit=50) if t["customer_id"] is not None][:10]
    monthly_sales = compute_monthly_series(session, company_id, [TransactionType.SALES_ORDER])

    return {
        "customer_count": len(customers),
        "total_revenue": financials.total_revenue,
        "customers": customers,
        "intelligence": intelligence,
        "recent_transactions": recent_transactions,
        "monthly_sales": monthly_sales,
    }
