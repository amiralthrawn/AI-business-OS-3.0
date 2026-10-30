from fastapi.testclient import TestClient

from app.business_context.service import BusinessContextService
from app.core.entities import Company, EventLogEntry
from app.database import get_db
from app.main import app


def _log_event(db_session, event_type: str, n: int = 1) -> None:
    import uuid
    from datetime import datetime, timezone

    for _ in range(n):
        db_session.add(
            EventLogEntry(
                event_id=uuid.uuid4(),
                event_type=event_type,
                payload={},
                source="human",
                correlation_id=uuid.uuid4(),
                occurred_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()


def test_no_suggestion_with_no_history(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    suggestions = BusinessContextService(db_session).suggest_configuration_changes(company.id)

    assert suggestions == []


def test_suggests_raising_notification_level_after_consistent_approvals(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    _log_event(db_session, "ActionApproved", n=2)

    suggestions = BusinessContextService(db_session).suggest_configuration_changes(company.id)

    assert len(suggestions) == 1
    assert suggestions[0].field == "notification_level"
    assert suggestions[0].suggested_value == "high"
    assert suggestions[0].evidence_count == 2


def test_suggests_lowering_notification_level_after_consistent_rejections(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    _log_event(db_session, "ActionRejected", n=2)

    suggestions = BusinessContextService(db_session).suggest_configuration_changes(company.id)

    assert len(suggestions) == 1
    assert suggestions[0].field == "notification_level"
    assert suggestions[0].suggested_value == "low"


def test_mixed_history_produces_no_suggestion(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    _log_event(db_session, "ActionApproved", n=2)
    _log_event(db_session, "ActionRejected", n=2)

    suggestions = BusinessContextService(db_session).suggest_configuration_changes(company.id)

    assert suggestions == []


def test_suggestion_is_never_applied_automatically(db_session):
    """The whole point: suggesting is not the same as changing. Only an
    explicit PATCH /business-context call (a human action) can change the
    stored configuration."""

    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    _log_event(db_session, "ActionApproved", n=5)

    service = BusinessContextService(db_session)
    service.suggest_configuration_changes(company.id)  # called, never applies anything

    context = service.get_or_create(company.id)
    assert context.notification_level == "normal"  # unchanged


def test_suggestions_api_endpoint(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    _log_event(db_session, "ActionApproved", n=2)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/business-context/suggestions")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["field"] == "notification_level"
    assert body[0]["suggested_value"] == "high"
