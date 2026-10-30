import inspect
import uuid

from fastapi.testclient import TestClient

from app.ai.orchestrator import service as orchestrator_module
from app.core.entities import Company, EventLogEntry, Product, Supplier, Task, TaskStatus
from app.database import get_db
from app.dependencies import get_event_bus
from app.event_bus import build_event_bus
from app.main import app


def _seed(db_session):
    company = Company(name="API Co")
    db_session.add(company)
    db_session.flush()
    supplier = Supplier(company_id=company.id, name="Pacific Components")
    db_session.add(supplier)
    db_session.flush()
    product = Product(company_id=company.id, supplier_id=supplier.id, name="Sensor Module", sku="PCB-011", unit_cost=61.0)
    db_session.add(product)
    db_session.commit()
    return supplier, product


def _override(db_session, session_factory):
    def override_get_db():
        yield db_session

    def override_get_event_bus():
        return build_event_bus(session_factory)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_event_bus] = override_get_event_bus


# --- AI cannot execute -------------------------------------------------------


def test_orchestrator_module_never_references_the_action_executor():
    source = inspect.getsource(orchestrator_module)
    assert "ActionExecutor" not in source
    assert "app.actions.executor" not in source


def test_full_scenario_ask_ai_only_proposes_never_executes(db_session, session_factory):
    supplier, product = _seed(db_session)
    _override(db_session, session_factory)
    client = TestClient(app)
    try:
        response = client.post(
            "/ai/ask",
            json={"question": "Crée une tâche pour revoir le fournisseur Pacific Components."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["requires_human_validation"] is True

    task_id = uuid.UUID(body["action_result"]["task_id"])
    task = db_session.get(Task, task_id)
    assert task.status == TaskStatus.PENDING_VALIDATION


# --- Approval / rejection through the real API --------------------------------


def test_ai_proposal_then_api_approval_creates_the_real_task_and_updates_home(db_session, session_factory):
    supplier, product = _seed(db_session)
    _override(db_session, session_factory)
    client = TestClient(app)
    try:
        ask_response = client.post(
            "/ai/ask",
            json={"question": "Crée une tâche pour revoir le fournisseur Pacific Components."},
        )
        task_id = ask_response.json()["action_result"]["task_id"]

        home_before = client.get("/home").json()
        assert home_before["tasks"]["pending_validation_tasks"] == 1

        approve_response = client.post(f"/actions/tasks/{task_id}/approve")

        home_after = client.get("/home").json()

        # A second approval must be rejected cleanly and must not duplicate anything.
        second_approve_response = client.post(f"/actions/tasks/{task_id}/approve")
    finally:
        app.dependency_overrides.clear()

    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "executed"

    assert home_after["tasks"]["pending_validation_tasks"] == 0
    event_types = {e["event_type"] for e in home_after["recent_events"]}
    assert {"ActionProposed", "ActionApproved", "ActionExecuted", "TaskCreated"} <= event_types

    assert second_approve_response.status_code == 400

    assert db_session.query(Task).filter_by(id=uuid.UUID(task_id)).count() == 1
    assert db_session.get(Task, uuid.UUID(task_id)).status == TaskStatus.EXECUTED


def test_ai_proposal_then_api_rejection_creates_no_task(db_session, session_factory):
    supplier, product = _seed(db_session)
    _override(db_session, session_factory)
    client = TestClient(app)
    try:
        ask_response = client.post(
            "/ai/ask",
            json={"question": "Crée une tâche pour revoir le fournisseur Pacific Components."},
        )
        task_id = ask_response.json()["action_result"]["task_id"]

        reject_response = client.post(f"/actions/tasks/{task_id}/reject")
        approve_after_reject_response = client.post(f"/actions/tasks/{task_id}/approve")
    finally:
        app.dependency_overrides.clear()

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert approve_after_reject_response.status_code == 400

    task = db_session.get(Task, uuid.UUID(task_id))
    assert task.status == TaskStatus.REJECTED


def test_approve_unknown_task_returns_404(db_session, session_factory):
    _override(db_session, session_factory)
    client = TestClient(app)
    try:
        response = client.post(f"/actions/tasks/{uuid.uuid4()}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


# --- 7. Traceability -----------------------------------------------------------


def test_correlation_id_links_proposal_approval_and_execution(db_session, session_factory):
    supplier, product = _seed(db_session)
    _override(db_session, session_factory)
    client = TestClient(app)
    try:
        ask_response = client.post(
            "/ai/ask",
            json={"question": "Crée une tâche pour revoir le fournisseur Pacific Components."},
        )
        task_id = ask_response.json()["action_result"]["task_id"]
        client.post(f"/actions/tasks/{task_id}/approve")
    finally:
        app.dependency_overrides.clear()

    task = db_session.get(Task, uuid.UUID(task_id))
    entries = db_session.query(EventLogEntry).filter_by(correlation_id=task.correlation_id).all()
    event_types = {e.event_type for e in entries}

    assert {"ActionProposed", "ActionApproved", "ActionExecuted", "TaskCreated"} <= event_types
