from fastapi.testclient import TestClient

from app.business_context.service import DEFAULT_MONITORED_DOMAINS, DEFAULT_NOTIFICATION_LEVEL, BusinessContextService
from app.core.entities import BusinessContext, Company
from app.database import get_db
from app.main import app


def test_get_or_create_returns_a_generic_default(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    context = BusinessContextService(db_session).get_or_create(company.id)

    assert context.monitored_domains == DEFAULT_MONITORED_DOMAINS
    assert context.notification_level == DEFAULT_NOTIFICATION_LEVEL
    assert context.stated_objectives is None


def test_get_or_create_is_idempotent(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    first = BusinessContextService(db_session).get_or_create(company.id)
    second = BusinessContextService(db_session).get_or_create(company.id)

    assert first.id == second.id
    assert db_session.query(BusinessContext).count() == 1


def test_update_only_changes_provided_fields(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()
    service = BusinessContextService(db_session)
    service.get_or_create(company.id)

    updated = service.update(company.id, stated_objectives="Grow revenue in core products.")

    assert updated.stated_objectives == "Grow revenue in core products."
    assert updated.monitored_domains == DEFAULT_MONITORED_DOMAINS  # untouched
    assert updated.notification_level == DEFAULT_NOTIFICATION_LEVEL  # untouched


def test_business_context_api_get_and_patch(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        get_response = client.get("/business-context")
        patch_response = client.patch(
            "/business-context",
            json={"notification_level": "high", "stated_objectives": "Win back BrightWorks Ltd."},
        )
    finally:
        app.dependency_overrides.clear()

    assert get_response.status_code == 200
    assert get_response.json()["monitored_domains"] == DEFAULT_MONITORED_DOMAINS

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["notification_level"] == "high"
    assert body["stated_objectives"] == "Win back BrightWorks Ltd."
    # Untouched by the PATCH, unlike a full replace would have done.
    assert body["monitored_domains"] == DEFAULT_MONITORED_DOMAINS


def test_business_context_api_without_a_company_returns_404(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/business-context")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
