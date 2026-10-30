"""A manual sweep that simulates what would be a scheduled job in production:
runs every deterministic monitoring rule against every relevant entity. No
Celery, Redis or cron here -- for the MVP this is invoked directly (at seed
time, and via POST /intelligence/monitor), which is enough to demonstrate the
detection logic. A real scheduler is a documented production bottleneck, not
solved by this step.
"""

from sqlalchemy.orm import Session

from app.core.entities import Customer, Product, Supplier
from app.core.events.bus import EventBus
from app.intelligence.opportunities.service import OpportunityDetectionService
from app.intelligence.risks.service import RiskDetectionService


def run_monitoring_sweep(session: Session, event_bus: EventBus) -> dict:
    risk_service = RiskDetectionService(session, event_bus)
    opportunity_service = OpportunityDetectionService(session, event_bus)

    risks_created = 0
    for product in session.query(Product).all():
        if risk_service.evaluate_margin_trend(product.id) is not None:
            risks_created += 1

    for supplier in session.query(Supplier).all():
        if risk_service.evaluate_supplier_delivery_performance(supplier.id) is not None:
            risks_created += 1

    opportunities_created = 0
    for customer in session.query(Customer).all():
        if risk_service.evaluate_customer_decline(customer.id) is not None:
            risks_created += 1
        if opportunity_service.evaluate_customer_growth(customer.id) is not None:
            opportunities_created += 1

    return {"risks_created": risks_created, "opportunities_created": opportunities_created}
