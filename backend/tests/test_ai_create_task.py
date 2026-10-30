import uuid

import pytest
from pydantic import ValidationError

from app.actions.service import ActionsService
from app.ai.capabilities import build_capability_registry
from app.ai.capabilities.base import CapabilityExecutionError
from app.ai.capabilities.create_task import CreateTaskInput, create_task_capability
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator
from app.core.entities import Company, Product, RelatedEntityType, Supplier, Task, TaskStatus


def _make_supplier_and_product(db_session, supplier_name="Pacific Components", unit_cost=61.0):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()

    supplier = Supplier(company_id=company.id, name=supplier_name)
    db_session.add(supplier)
    db_session.flush()

    product = Product(company_id=company.id, supplier_id=supplier.id, name="Sensor Module", sku="PCB-011", unit_cost=unit_cost)
    db_session.add(product)
    db_session.commit()

    return supplier, product


# --- A. Capability registry -------------------------------------------------


def test_create_task_is_registered_as_an_action_requiring_human_validation():
    registry = build_capability_registry()

    capability = registry.get("create_task")

    assert capability.kind == "action"
    assert capability.requires_human_validation is True


# --- B. create_task behavior -------------------------------------------------


def test_create_task_capability_creates_a_pending_validation_task(db_session, event_bus):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    result = create_task_capability.run(
        db_session,
        event_bus=event_bus,
        company_id=company.id,
        title="Review supplier Pacific Components",
    )

    assert result.status == "pending_validation"
    assert result.requires_human_validation is True

    task = db_session.get(Task, result.task_id)
    assert task is not None
    assert task.status == TaskStatus.PENDING_VALIDATION


def test_create_task_capability_delegates_to_actions_service_not_raw_sql(db_session, event_bus, monkeypatch):
    calls = []
    original = ActionsService.propose_task

    def spy(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(ActionsService, "propose_task", spy)

    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    create_task_capability.run(
        db_session,
        event_bus=event_bus,
        company_id=company.id,
        title="Review supplier Pacific Components",
    )

    assert len(calls) == 1
    assert calls[0]["title"] == "Review supplier Pacific Components"
    assert calls[0]["pending_action"] == "create_task"


def test_create_task_capability_rejects_an_unknown_company(db_session, event_bus):
    with pytest.raises(CapabilityExecutionError):
        create_task_capability.run(
            db_session, event_bus=event_bus, company_id=uuid.uuid4(), title="Review supplier X"
        )


def test_create_task_capability_requires_an_event_bus(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    with pytest.raises(CapabilityExecutionError):
        create_task_capability.run(db_session, company_id=company.id, title="Review supplier X")


# --- C. AI orchestration -----------------------------------------------------


def test_ai_task_creation_request_routes_to_procurement_and_creates_pending_task(db_session, event_bus):
    supplier, product = _make_supplier_and_product(db_session)
    orchestrator = AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), event_bus)

    result = orchestrator.ask("Crée une tâche pour revoir le fournisseur Pacific Components.")

    assert result.agent == "procurement"
    assert "create_task" in result.capabilities_used
    assert result.requires_human_validation is True
    assert result.action_result is not None
    assert result.action_result["status"] == "pending_validation"

    task = db_session.query(Task).filter_by(related_entity_id=supplier.id).one()
    assert task.status == TaskStatus.PENDING_VALIDATION
    assert task.related_entity_type == RelatedEntityType.SUPPLIER
    assert task.company_id == supplier.company_id


def test_ai_task_creation_request_does_not_run_the_analytical_capabilities(db_session, event_bus):
    _make_supplier_and_product(db_session)
    orchestrator = AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), event_bus)

    result = orchestrator.ask("Crée une tâche pour revoir le fournisseur Pacific Components.")

    assert "read_transactions" not in result.capabilities_used
    assert "analyze_margin" not in result.capabilities_used


# --- D. Safety / side effect --------------------------------------------------


def test_create_task_input_schema_has_no_status_field(db_session):
    with pytest.raises(ValidationError):
        CreateTaskInput(company_id=uuid.uuid4(), title="Review supplier X", status="done")


def test_actions_service_create_task_has_no_status_parameter(db_session, event_bus):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    with pytest.raises(TypeError):
        ActionsService(db_session, event_bus).propose_task(
            company_id=company.id, title="Review supplier X", status=TaskStatus.DONE
        )

    # Nothing was created by the rejected call above.
    assert db_session.query(Task).count() == 0
