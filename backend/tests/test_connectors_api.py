from fastapi.testclient import TestClient

from app.core.entities import Company
from app.database import get_db
from app.main import app


def _client_with(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_list_connectors_returns_the_three_registered_types(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    client = _client_with(db_session)
    try:
        response = client.get("/connectors")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    connectors = {c["connector"] for c in response.json()["connectors"]}
    assert connectors == {"email", "calendar", "website"}


def test_sync_email_connector_returns_a_summary_and_ingests_data(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    client = _client_with(db_session)
    try:
        response = client.post("/connectors/email/sync")
        status_response = client.get("/connectors/email/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["connector"] == "email"
    assert body["created"] > 0
    assert body["fetched"] == body["created"] + body["skipped"]

    assert status_response.status_code == 200
    assert status_response.json()["ingested_count"] == body["created"]


def test_sync_twice_is_idempotent_via_the_api(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    client = _client_with(db_session)
    try:
        first = client.post("/connectors/website/sync").json()
        second = client.post("/connectors/website/sync").json()
    finally:
        app.dependency_overrides.clear()

    assert second["created"] == 0
    assert second["skipped"] == first["created"]


def test_sync_unknown_connector_type_returns_404(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.commit()

    client = _client_with(db_session)
    try:
        response = client.post("/connectors/sms/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_sync_with_no_company_returns_404(db_session):
    client = _client_with(db_session)
    try:
        response = client.post("/connectors/email/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
