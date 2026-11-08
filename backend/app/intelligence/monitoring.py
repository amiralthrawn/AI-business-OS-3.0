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


def run_monitoring_sweep(session: Session, event_bus: EventBus, report=None) -> dict:
    """`report(text, percent)` is told where the sweep is (and may raise to stop it)."""

    report = report or (lambda text, percent: None)
    products = session.query(Product).all()
    suppliers = session.query(Supplier).all()
    customers = session.query(Customer).all()
    total = max(1, len(products) + len(suppliers) + len(customers))
    done = 0

    def tick(text: str) -> None:
        nonlocal done
        done += 1
        if done % 10 == 1 or done == total:
            report(text.format(done=done), int(100 * done / total))

    risk_service = RiskDetectionService(session, event_bus)
    opportunity_service = OpportunityDetectionService(session, event_bus)

    risks_created = 0
    for product in products:
        tick(f"Marges produit : {{done}} sur {total} éléments vérifiés ({len(products)} produits)")
        if risk_service.evaluate_margin_trend(product.id) is not None:
            risks_created += 1

    for supplier in suppliers:
        tick(f"Délais et prix fournisseurs : {{done}} sur {total} éléments vérifiés ({len(suppliers)} fournisseurs)")
        if risk_service.evaluate_supplier_delivery_performance(supplier.id) is not None:
            risks_created += 1

    opportunities_created = 0
    for customer in customers:
        tick(f"Activité des clients : {{done}} sur {total} éléments vérifiés ({len(customers)} clients)")
        if risk_service.evaluate_customer_decline(customer.id) is not None:
            risks_created += 1
        if opportunity_service.evaluate_customer_growth(customer.id) is not None:
            opportunities_created += 1

    return {"risks_created": risks_created, "opportunities_created": opportunities_created}
