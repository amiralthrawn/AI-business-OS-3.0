import uuid

from fastapi.testclient import TestClient

from app.core.entities import Company, Opportunity, OpportunityStatus
from app.database import get_db
from app.main import app


def test_list_and_get_opportunity(db_session):
    company = Company(name="Acme")
    db_session.add(company)
    db_session.flush()
    opportunity = Opportunity(
        company_id=company.id, title="Growing customer: Metroline Corp", status=OpportunityStatus.OPEN
    )
    db_session.add(opportunity)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        list_response = client.get("/intelligence/opportunities")
        detail_response = client.get(f"/intelligence/opportunities/{opportunity.id}")
        missing_response = client.get(f"/intelligence/opportunities/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert any(o["id"] == str(opportunity.id) for o in list_response.json())

    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Growing customer: Metroline Corp"

    assert missing_response.status_code == 404
