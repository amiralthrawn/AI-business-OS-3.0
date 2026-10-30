from fastapi.testclient import TestClient

from app.core.entities import Company
from app.database import get_db
from app.main import app


def test_company_api_get_and_patch(db_session):
    company = Company(name="Acme Manufacturing", industry="Industrial equipment")
    db_session.add(company)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        get_response = client.get("/company")
        patch_response = client.patch("/company", json={"name": "Northwind Fabrication"})
    finally:
        app.dependency_overrides.clear()

    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Acme Manufacturing"
    assert get_response.json()["industry"] == "Industrial equipment"

    assert patch_response.status_code == 200
    body = patch_response.json()
    assert body["name"] == "Northwind Fabrication"
    assert body["industry"] == "Industrial equipment"  # untouched by the PATCH


def test_company_api_patch_only_changes_provided_fields(db_session):
    company = Company(name="Acme Manufacturing", industry="Industrial equipment")
    db_session.add(company)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).patch("/company", json={"industry": "Steel distribution"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["industry"] == "Steel distribution"
    assert body["name"] == "Acme Manufacturing"


def test_company_api_without_a_company_returns_404(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/company")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
