import pytest

from app.core.entities import Company, EventLogEntry, Product, Supplier
from app.core.events.bus import InProcessEventBus
from app.core.events.log_handler import make_event_log_handler
from app.domains.procurement.service import SUPPLIER_COST_INCREASED, ProcurementError, ProcurementService


def _make_supplier_and_product(db_session, unit_cost=100.0):
    company = Company(name="Test Co")
    db_session.add(company)
    db_session.flush()

    supplier = Supplier(company_id=company.id, name="Test Supplier")
    db_session.add(supplier)
    db_session.flush()

    product = Product(company_id=company.id, supplier_id=supplier.id, name="Widget", sku="W-1", unit_cost=unit_cost)
    db_session.add(product)
    db_session.commit()

    return supplier, product


def _bus_with_log(session_factory):
    bus = InProcessEventBus()
    bus.subscribe("*", make_event_log_handler(session_factory))
    return bus


def test_record_supplier_cost_increase_publishes_a_correct_event(db_session, session_factory):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=100.0)
    bus = _bus_with_log(session_factory)
    service = ProcurementService(db_session, bus)

    event = service.record_supplier_cost_increase(supplier.id, product.id, new_unit_cost=110.0)

    assert event.event_type == SUPPLIER_COST_INCREASED
    assert event.source == "procurement"
    assert event.correlation_id is not None
    assert event.payload["supplier_id"] == str(supplier.id)
    assert event.payload["product_id"] == str(product.id)
    assert event.payload["old_unit_cost"] == 100.0
    assert event.payload["new_unit_cost"] == 110.0
    assert event.payload["variation_pct"] == pytest.approx(0.10)


def test_service_updates_the_existing_product_in_place(db_session, session_factory):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=50.0)
    bus = _bus_with_log(session_factory)
    service = ProcurementService(db_session, bus)

    service.record_supplier_cost_increase(supplier.id, product.id, new_unit_cost=60.0)

    db_session.refresh(product)
    assert product.unit_cost == 60.0
    # No new Product/Supplier row created -- Procurement reuses the Data Core entity.
    assert db_session.query(Product).count() == 1
    assert db_session.query(Supplier).count() == 1


def test_event_is_persisted_exactly_once_in_event_log(db_session, session_factory):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=100.0)
    bus = _bus_with_log(session_factory)
    service = ProcurementService(db_session, bus)

    event = service.record_supplier_cost_increase(supplier.id, product.id, new_unit_cost=120.0)

    entries = db_session.query(EventLogEntry).filter_by(event_id=event.event_id).all()
    assert len(entries) == 1
    assert entries[0].event_type == SUPPLIER_COST_INCREASED
    assert entries[0].payload["variation_pct"] == pytest.approx(0.20)

    # Re-publishing the exact same event must not create a duplicate log entry
    # (existing InProcessEventBus double-processing protection).
    bus.publish(event)
    assert db_session.query(EventLogEntry).filter_by(event_id=event.event_id).count() == 1


def test_rejects_a_decrease_or_equal_cost(db_session, session_factory):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=100.0)
    bus = _bus_with_log(session_factory)
    service = ProcurementService(db_session, bus)

    with pytest.raises(ProcurementError):
        service.record_supplier_cost_increase(supplier.id, product.id, new_unit_cost=100.0)
    with pytest.raises(ProcurementError):
        service.record_supplier_cost_increase(supplier.id, product.id, new_unit_cost=90.0)


def test_rejects_a_product_not_owned_by_the_supplier(db_session, session_factory):
    supplier, product = _make_supplier_and_product(db_session, unit_cost=100.0)
    other_supplier = Supplier(company_id=product.company_id, name="Other Supplier")
    db_session.add(other_supplier)
    db_session.commit()

    bus = _bus_with_log(session_factory)
    service = ProcurementService(db_session, bus)

    with pytest.raises(ProcurementError):
        service.record_supplier_cost_increase(other_supplier.id, product.id, new_unit_cost=150.0)
