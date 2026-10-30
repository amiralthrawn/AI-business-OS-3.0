"""Business Domain read views (Step 23B): Supplier/Customer/Product/
Transaction list + detail, composed entirely from existing functions --
`app.core.entity_context.get_entity_context` for relational structure,
`HomeService.get_ai_priorities` for AI signals, and `app.core.analytics`'s
existing trend functions for the one domain metric each entity type already
has. No new computation, no new source of truth: every non-trivial number
here was already being computed somewhere in the system before this file
existed.
"""

import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.analytics import (
    compute_customer_value_trend,
    compute_margin_trend,
    compute_supplier_delivery_performance,
    compute_unanswered_message_age,
)
from app.core.entities import Communication, Contact, Customer, Product, RelatedEntityType, Supplier, Transaction
from app.core.entity_context import get_entity_context
from app.home.service import HomeService


def _intelligence_by_entity(session: Session, company_id: uuid.UUID) -> dict[tuple, list[dict]]:
    """One Business State Snapshot build, reused across every row of a list
    view -- never rebuilt per entity. Same data Home's own "AI Priorities"
    section already shows, just indexed by entity here."""

    signals = HomeService(session).get_ai_priorities(company_id, limit=1000)
    by_entity: dict[tuple, list[dict]] = defaultdict(list)
    for signal in signals:
        by_entity[(signal["entity_type"], signal["entity_id"])].append(signal)
    return by_entity


def _transaction_dict(t: Transaction) -> dict:
    return {
        "id": t.id,
        "type": t.type.value,
        "status": t.status.value,
        "amount": t.amount,
        "currency": t.currency,
        "occurred_at": t.occurred_at,
        "expected_at": t.expected_at,
        "supplier_id": t.supplier_id,
        "supplier_name": t.supplier.name if t.supplier is not None else None,
        "customer_id": t.customer_id,
        "customer_name": t.customer.name if t.customer is not None else None,
        "product_id": t.product_id,
        "product_name": t.product.name if t.product is not None else None,
    }


def list_suppliers(session: Session, company_id: uuid.UUID) -> list[dict]:
    intelligence = _intelligence_by_entity(session, company_id)
    suppliers = session.query(Supplier).filter_by(company_id=company_id).order_by(Supplier.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "country": s.country,
            "product_count": len(s.products),
            "transaction_count": len(s.transactions),
            "signal_count": len(intelligence.get((RelatedEntityType.SUPPLIER, s.id), [])),
            "top_signal": (intelligence.get((RelatedEntityType.SUPPLIER, s.id)) or [None])[0],
        }
        for s in suppliers
    ]


def get_supplier_detail(session: Session, company_id: uuid.UUID, supplier_id: uuid.UUID) -> dict | None:
    supplier = session.query(Supplier).filter_by(id=supplier_id, company_id=company_id).first()
    if supplier is None:
        return None

    context = get_entity_context(session, RelatedEntityType.SUPPLIER, supplier_id)
    performance = compute_supplier_delivery_performance(session, supplier_id)
    unanswered = compute_unanswered_message_age(session, RelatedEntityType.SUPPLIER, supplier_id)
    intelligence = _intelligence_by_entity(session, company_id).get((RelatedEntityType.SUPPLIER, supplier_id), [])

    return {
        **context,
        "id": supplier.id,  # get_entity_context's own key is `entity_id`, not `id`
        "intelligence": intelligence,
        "delivery_trend": performance.trend,
        "baseline_avg_delay_days": performance.baseline_avg_delay_days,
        "recent_avg_delay_days": performance.recent_avg_delay_days,
        "unanswered_message_age_days": unanswered.age_days,
    }


def list_customers(session: Session, company_id: uuid.UUID) -> list[dict]:
    intelligence = _intelligence_by_entity(session, company_id)
    customers = session.query(Customer).filter_by(company_id=company_id).order_by(Customer.name).all()
    items = []
    for c in customers:
        trend = compute_customer_value_trend(session, c.id)
        items.append(
            {
                "id": c.id,
                "name": c.name,
                "country": c.country,
                "transaction_count": len(c.transactions),
                "recent_revenue": trend.recent_revenue,
                "signal_count": len(intelligence.get((RelatedEntityType.CUSTOMER, c.id), [])),
                "top_signal": (intelligence.get((RelatedEntityType.CUSTOMER, c.id)) or [None])[0],
            }
        )
    return items


def get_customer_detail(session: Session, company_id: uuid.UUID, customer_id: uuid.UUID) -> dict | None:
    customer = session.query(Customer).filter_by(id=customer_id, company_id=company_id).first()
    if customer is None:
        return None

    context = get_entity_context(session, RelatedEntityType.CUSTOMER, customer_id)
    trend = compute_customer_value_trend(session, customer_id)
    unanswered = compute_unanswered_message_age(session, RelatedEntityType.CUSTOMER, customer_id)
    intelligence = _intelligence_by_entity(session, company_id).get((RelatedEntityType.CUSTOMER, customer_id), [])

    return {
        **context,
        "id": customer.id,
        "intelligence": intelligence,
        "revenue_trend": trend.trend,
        "baseline_revenue": trend.baseline_revenue,
        "recent_revenue": trend.recent_revenue,
        "variation_pct": trend.variation_pct,
        "unanswered_message_age_days": unanswered.age_days,
    }


def list_products(session: Session, company_id: uuid.UUID) -> list[dict]:
    intelligence = _intelligence_by_entity(session, company_id)
    products = session.query(Product).filter_by(company_id=company_id).order_by(Product.name).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "unit_cost": p.unit_cost,
            "supplier": {"id": p.supplier.id, "name": p.supplier.name} if p.supplier is not None else None,
            "transaction_count": len(p.transactions),
            "signal_count": len(intelligence.get((RelatedEntityType.PRODUCT, p.id), [])),
        }
        for p in products
    ]


def get_product_detail(session: Session, company_id: uuid.UUID, product_id: uuid.UUID) -> dict | None:
    product = session.query(Product).filter_by(id=product_id, company_id=company_id).first()
    if product is None:
        return None

    context = get_entity_context(session, RelatedEntityType.PRODUCT, product_id)
    trend = compute_margin_trend(session, product_id)
    intelligence = _intelligence_by_entity(session, company_id).get((RelatedEntityType.PRODUCT, product_id), [])

    return {
        **context,
        "id": product.id,
        "intelligence": intelligence,
        "margin_trend": trend.trend,
        "baseline_margin_pct": trend.baseline_margin_pct,
        "recent_margin_pct": trend.recent_margin_pct,
    }


def list_contacts(session: Session, company_id: uuid.UUID) -> list[dict]:
    contacts = session.query(Contact).filter_by(company_id=company_id).order_by(Contact.name).all()

    related_name: str | None
    items = []
    for c in contacts:
        related_name = None
        if c.related_entity_type == RelatedEntityType.SUPPLIER and c.related_entity_id is not None:
            entity = session.query(Supplier).filter_by(id=c.related_entity_id).first()
            related_name = entity.name if entity is not None else None
        elif c.related_entity_type == RelatedEntityType.CUSTOMER and c.related_entity_id is not None:
            entity = session.query(Customer).filter_by(id=c.related_entity_id).first()
            related_name = entity.name if entity is not None else None

        last_comm = None
        if c.related_entity_type is not None and c.related_entity_id is not None:
            last_comm = (
                session.query(Communication)
                .filter_by(related_entity_type=c.related_entity_type, related_entity_id=c.related_entity_id)
                .order_by(Communication.occurred_at.desc())
                .first()
            )

        items.append(
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "email": c.email,
                "phone": c.phone,
                "related_entity_type": c.related_entity_type.value if c.related_entity_type else None,
                "related_entity_id": c.related_entity_id,
                "related_entity_name": related_name,
                "last_communication": (
                    {
                        "id": last_comm.id,
                        "channel": last_comm.channel,
                        "channel_detail": last_comm.channel_detail,
                        "direction": last_comm.direction.value,
                        "subject": last_comm.subject,
                        "occurred_at": last_comm.occurred_at,
                    }
                    if last_comm is not None
                    else None
                ),
            }
        )
    return items


def list_transactions(session: Session, company_id: uuid.UUID, limit: int = 100) -> list[dict]:
    rows = (
        session.query(Transaction)
        .filter_by(company_id=company_id)
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [_transaction_dict(t) for t in rows]


def get_transaction_detail(session: Session, company_id: uuid.UUID, transaction_id: uuid.UUID) -> dict | None:
    transaction = session.query(Transaction).filter_by(id=transaction_id, company_id=company_id).first()
    if transaction is None:
        return None
    return _transaction_dict(transaction)
