"""V3 step 3: Home is cut on the server to what each profile may see."""

import pytest

from app.config import get_settings
from tests.v2_support import api_client

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def required_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "required")


@pytest.fixture()
def client(session_factory):
    with api_client(session_factory) as c:
        yield c


def _signup(client):
    res = client.post("/auth/signup", json={"company_name": "Alpha", "name": "Alice Dir", "email": "a@alpha.example", "password": PASSWORD})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _invited(client, director, role, email):
    created = client.post("/users", headers=director, json={"name": role.title(), "role": role, "email": email, "job_title": "Poste"})
    assert created.status_code in (200, 201), created.text
    token = client.post(f"/users/{created.json()['id']}/invite", headers=director).json()["invite_url"].rsplit("/", 1)[-1]
    session = client.post(f"/auth/invitations/{token}/accept", json={"password": PASSWORD}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_home_has_a_briefing_and_names_what_the_viewer_can_see(client):
    director = _signup(client)
    home = client.get("/home", headers=director).json()
    assert home["viewer"]["role"] and "Finance" in home["viewer"]["areas"]
    assert home["briefing"]["headline"]
    # A new company with no data is told to import its data, not shown demo content.
    assert any("Importez" in line for line in home["briefing"]["lines"])


def test_an_employee_does_not_get_the_finance_or_intelligence_picture(client, db_session):
    director = _signup(client)
    employee = _invited(client, director, "employee", "e@alpha.example")
    home = client.get("/home", headers=employee).json()
    assert "Finance" not in home["viewer"]["areas"]
    assert home["priorities"] == [] and home["decisions"] == [] and home["recent_events"] == []
    assert home["risks"]["total_risks"] == 0 and home["opportunities"]["total_opportunities"] == 0
    assert home["overview"]["transaction_count"] == 0


def _payload():
    prio = lambda domain: {"kind": "risk", "domain": domain, "title": f"{domain} risk"}
    return {
        "overview": {"supplier_count": 3, "product_count": 4, "customer_count": 5, "transaction_count": 6},
        "priorities": [prio("finance"), prio("sales"), prio("procurement")],
        "decisions": [{"domain": "finance"}, {"domain": "sales"}],
        "risks": {"total_risks": 2, "high_risks": 1, "recent_risks": ["x"]},
        "opportunities": {"total_opportunities": 1, "recent_opportunities": ["y"]},
        "tasks": {"total_tasks": 1, "pending_validation_tasks": 1, "recent_tasks": ["t"]},
        "recent_events": ["e"],
        "os_activity": [{"domain": "finance"}, {"domain": "sales"}, {"domain": None}],
        "company_narrative": ["n"],
    }


def test_scope_home_cuts_each_role_to_its_own_domains():
    from app.access.deps import CurrentUser
    from app.core.entities import Role
    from app.home.scoping import scope_home

    sales = scope_home(_payload(), CurrentUser(role=Role.SALES, profile=None))
    assert [p["domain"] for p in sales["priorities"]] == ["finance", "sales"]  # sales also reads finance, not procurement
    assert [d["domain"] for d in sales["decisions"]] == ["finance", "sales"]

    accountant = scope_home(_payload(), CurrentUser(role=Role.ACCOUNTANT, profile=None))
    assert {p["domain"] for p in accountant["priorities"]} == {"finance", "sales", "procurement"}

    employee = scope_home(_payload(), CurrentUser(role=Role.EMPLOYEE, profile=None))
    assert employee["priorities"] == [] and employee["decisions"] == [] and employee["recent_events"] == []
    assert employee["risks"]["total_risks"] == 0 and employee["opportunities"]["total_opportunities"] == 0
    assert employee["overview"]["transaction_count"] == 0


def test_pending_approvals_on_home_are_only_those_the_person_can_approve(client, db_session):
    from app.core.entities import Company, Task
    from app.core.entities.task import TaskStatus

    director = _signup(client)
    company = db_session.query(Company).one()
    for domain in ("finance", "sales", "procurement"):
        db_session.add(Task(company_id=company.id, title=f"{domain} task", description="x", status=TaskStatus.PENDING_VALIDATION, domain=domain))
    db_session.commit()
    assert client.get("/home", headers=director).json()["tasks"]["pending_validation_tasks"] == 3
    sales = _invited(client, director, "sales", "s@alpha.example")
    tasks = client.get("/home", headers=sales).json()["tasks"]
    assert tasks["pending_validation_tasks"] == 1
    assert [t["domain"] for t in tasks["recent_tasks"]] == ["sales"]


def test_task_list_and_bell_follow_the_profile(client, db_session):
    from app.core.entities import Company, Task
    from app.core.entities.task import TaskStatus

    director = _signup(client)
    company = db_session.query(Company).one()
    for domain in ("finance", "sales", "procurement"):
        db_session.add(Task(company_id=company.id, title=f"{domain} task", description="x", status=TaskStatus.PENDING_VALIDATION, domain=domain))
    db_session.commit()
    assert client.get("/actions/tasks/pending-count", headers=director).json() == {"count": 3}
    sales = _invited(client, director, "sales", "s2@alpha.example")
    assert client.get("/actions/tasks/pending-count", headers=sales).json() == {"count": 1}
    assert {t["domain"] for t in client.get("/actions/tasks", headers=sales).json()} == {"finance", "sales"}  # sales may read finance, not procurement
