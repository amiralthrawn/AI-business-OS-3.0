"""Finance domain overview (Step 23B): a company-wide Finance view composed
entirely from existing functions -- `app.core.analytics.compute_company_financials`
for the totals, `compute_margin_trend` per product (already used by
app.data.service for the Product detail page), `HomeService.get_ai_priorities`
filtered to the "finance" domain for intelligence, and `app.data.service.list_transactions`
for recent activity. No new source of truth is introduced here.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.analytics import compute_company_financials, compute_margin_trend, compute_monthly_series
from app.core.entities import Product, Transaction, TransactionType
from app.data.service import list_transactions
from app.home.service import HomeService

_EMPTY_OVERVIEW: dict = {
    "total_revenue": 0.0,
    "total_costs": 0.0,
    "overall_margin_pct": None,
    "transaction_count": 0,
    "products": [],
    "intelligence": [],
    "recent_transactions": [],
    "monthly_purchases": [],
    "monthly_sales": [],
}


def get_finance_overview(session: Session, company_id: uuid.UUID | None) -> dict:
    if company_id is None:
        return dict(_EMPTY_OVERVIEW)

    financials = compute_company_financials(session, company_id)

    products = session.query(Product).filter_by(company_id=company_id).order_by(Product.name).all()
    product_margins = []
    for product in products:
        trend = compute_margin_trend(session, product.id)
        if trend.sample_size == 0:
            continue  # nothing to show for a product with no sales orders at all
        product_margins.append(
            {
                "id": product.id,
                "name": product.name,
                "margin_trend": trend.trend,
                "recent_margin_pct": trend.recent_margin_pct,
            }
        )

    intelligence = [
        s for s in HomeService(session).get_ai_priorities(company_id, limit=1000) if s["domain"] == "finance"
    ]

    return {
        "total_revenue": financials.total_revenue,
        "total_costs": financials.total_costs,
        "overall_margin_pct": financials.overall_margin_pct,
        "transaction_count": session.query(Transaction).filter_by(company_id=company_id).count(),
        "products": product_margins,
        "intelligence": intelligence,
        "recent_transactions": list_transactions(session, company_id, limit=10),
        # Same two series as Procurement/Sales' own overviews -- the
        # Finance page cross-references them on one chart (Step 29 point 11)
        # rather than recomputing anything new.
        "monthly_purchases": compute_monthly_series(session, company_id, [TransactionType.PURCHASE_ORDER, TransactionType.INVOICE]),
        "monthly_sales": compute_monthly_series(session, company_id, [TransactionType.SALES_ORDER]),
    }
