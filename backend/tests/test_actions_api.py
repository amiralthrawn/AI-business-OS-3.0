import uuid

from fastapi.testclient import TestClient

from app.core.entities import Company, EventLogEntry, Product, Risk, Supplier, Task, TaskStatus
from app.database import get_db
from app.dependencies import get_event_bus
from app.event_bus import build_event_bus
from app.main import app


def test_create_task_api_creates_an_open_task_not_pending_validation(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="API Supplier")
    db_session.add(supplier)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        response = TestClient(app).post(
            "/actions/tasks",
            json={
                "title": "Contacter API Supplier",
                "description": "Suite à la révision tarifaire.",
                "related_entity_type": "supplier",
                "related_entity_id": str(supplier.id),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Contacter API Supplier"
    assert body["status"] == "open"
    assert body["pending_action"] is None  # never eligible for approve/reject -- it's not an AI proposal

    task = db_session.get(Task, uuid.UUID(body["id"]))
    assert task.status == TaskStatus.OPEN


def test_update_task_status_moves_an_open_task_to_in_progress_then_done(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.commit()
    task = Task(company_id=company.id, title="Analyser un problème opérationnel", status=TaskStatus.OPEN, domain="operations")
    db_session.add(task)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        response = client.post(f"/actions/tasks/{task.id}/status", json={"status": "in_progress"})
        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

        response = client.post(f"/actions/tasks/{task.id}/status", json={"status": "done"})
        assert response.status_code == 200
        assert response.json()["status"] == "done"
    finally:
        app.dependency_overrides.clear()

    db_session.refresh(task)
    assert task.status == TaskStatus.DONE


def test_update_task_status_rejects_an_invalid_transition(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.commit()
    task = Task(company_id=company.id, title="Préparer un rapport financier", status=TaskStatus.DONE, domain="finance")
    db_session.add(task)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        response = TestClient(app).post(f"/actions/tasks/{task.id}/status", json={"status": "in_progress"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_update_task_status_rejects_an_ai_proposal_awaiting_validation(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.commit()
    task = Task(
        company_id=company.id,
        title="Proposition IA",
        status=TaskStatus.PENDING_VALIDATION,
        pending_action="create_task",
    )
    db_session.add(task)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        response = TestClient(app).post(f"/actions/tasks/{task.id}/status", json={"status": "done"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_submit_task_for_validation_then_approve_marks_it_executed(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.commit()
    task = Task(
        company_id=company.id,
        title="Analyser une demande de financement",
        status=TaskStatus.OPEN,
        domain="finance",
        requires_decision=True,
    )
    db_session.add(task)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        response = client.post(f"/actions/tasks/{task.id}/submit")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending_validation"
        assert body["pending_action"] == "create_task"

        response = client.post(f"/actions/tasks/{task.id}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "executed"
    finally:
        app.dependency_overrides.clear()


def test_submit_task_for_validation_rejects_a_task_already_pending(db_session, session_factory):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.commit()
    task = Task(company_id=company.id, title="Proposition IA", status=TaskStatus.PENDING_VALIDATION, pending_action="create_task")
    db_session.add(task)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        response = TestClient(app).post(f"/actions/tasks/{task.id}/submit")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_create_task_api_without_a_company_returns_404(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post("/actions/tasks", json={"title": "Orphan task"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def _seed_and_trigger(db_session, session_factory, new_unit_cost=140.0):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="API Supplier")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Gadget", sku="G-1", unit_cost=100.0)
    db_session.add(product)
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus
    try:
        client = TestClient(app)
        response = client.post(
            "/procurement/supplier-cost-changes",
            json={
                "supplier_id": str(supplier.id),
                "product_id": str(product.id),
                "new_unit_cost": new_unit_cost,
            },
        )
    finally:
        app.dependency_overrides.clear()

    return response, supplier, product


def test_full_chain_through_the_api_creates_a_pending_validation_task(db_session, session_factory):
    response, supplier, product = _seed_and_trigger(db_session, session_factory)
    assert response.status_code == 200
    event_id = uuid.UUID(response.json()["event_id"])

    risk = db_session.query(Risk).filter_by(source_event_id=event_id).one()
    task = db_session.query(Task).filter_by(related_entity_id=supplier.id).one()

    assert task.status == TaskStatus.PENDING_VALIDATION
    assert task.related_entity_id == supplier.id

    logged_types = {e.event_type for e in db_session.query(EventLogEntry).all()}
    assert {"SupplierCostIncreased", "RiskCreated", "TaskCreated"} <= logged_types

    client = TestClient(app)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        list_response = client.get("/actions/tasks")
        detail_response = client.get(f"/actions/tasks/{task.id}")
        missing_response = client.get(f"/actions/tasks/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert any(t["id"] == str(task.id) for t in list_response.json())

    assert detail_response.status_code == 200
    body = detail_response.json()
    assert body["status"] == "pending_validation"
    assert body["related_entity_id"] == str(supplier.id)

    assert missing_response.status_code == 404
