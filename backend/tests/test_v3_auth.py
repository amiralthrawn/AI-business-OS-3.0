"""V3: sign-in, invitations, company-defined roles and company isolation.

Runs with AUTH_MODE=required (the production default), on two companies that
share one database -- exactly what a hosted multi-customer deployment does.
"""

import uuid

import pytest

from app.auth.security import hash_password, verify_password
from app.config import get_settings
from app.core.entities import Company, Customer, Supplier, UserProfile
from app.core.tenant_scope import CrossTenantWriteError, scope_session
from tests.v2_support import api_client

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def required_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "required")


@pytest.fixture()
def client(session_factory):
    with api_client(session_factory) as c:
        yield c


def _signup(client, company="Négoce Alpha", email="dirigeant@alpha.example", name="Alice Directrice"):
    res = client.post("/auth/signup", json={"company_name": company, "name": name, "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    return res.json()


def _auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


# --- Passwords and sign-in ---------------------------------------------------


def test_password_hashes_verify_and_never_store_the_password():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and stored.startswith("scrypt$")
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong password!", stored)
    assert not verify_password(PASSWORD, None)


def test_every_api_route_needs_a_token_except_auth_and_health(client):
    assert client.get("/health").status_code == 200
    for path in ("/home", "/company", "/suppliers", "/users/me", "/actions/tasks", "/business-context"):
        res = client.get(path)
        assert res.status_code == 401, path
        assert res.headers.get("www-authenticate") == "Bearer"
    assert client.get("/home", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_x_user_id_is_ignored_once_sign_in_is_required(client, db_session):
    session = _signup(client)
    assert client.get("/users/me", headers={"X-User-Id": session["profile_id"]}).status_code == 401


def test_signup_creates_a_company_and_its_director(client, db_session):
    session = _signup(client)
    me = client.get("/users/me", headers=_auth(session)).json()
    assert me["role"] == "director"
    assert me["profile"]["email"] == "dirigeant@alpha.example"
    assert me["profile"]["account_status"] == "active"
    assert client.get("/company", headers=_auth(session)).json()["name"] == "Négoce Alpha"


def test_signup_rejects_short_passwords_and_taken_emails(client):
    weak = client.post("/auth/signup", json={"company_name": "X", "name": "Y", "email": "y@x.example", "password": "short"})
    assert weak.status_code == 400
    _signup(client)
    again = client.post(
        "/auth/signup",
        json={"company_name": "Other", "name": "Z", "email": "DIRIGEANT@alpha.example", "password": PASSWORD},
    )
    assert again.status_code == 409


def test_signup_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "signup_enabled", False)
    res = client.post("/auth/signup", json={"company_name": "X", "name": "Y", "email": "y@x.example", "password": PASSWORD})
    assert res.status_code == 403


def test_login_checks_the_password_and_the_account_state(client, db_session):
    _signup(client)
    ok = client.post("/auth/login", json={"email": " Dirigeant@Alpha.example ", "password": PASSWORD})
    assert ok.status_code == 200
    assert client.get("/users/me", headers=_auth(ok.json())).status_code == 200
    assert client.post("/auth/login", json={"email": "dirigeant@alpha.example", "password": "wrong password"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@alpha.example", "password": PASSWORD}).status_code == 401

    profile = db_session.query(UserProfile).filter_by(email="dirigeant@alpha.example").one()
    profile.is_active = False
    db_session.commit()
    assert client.post("/auth/login", json={"email": "dirigeant@alpha.example", "password": PASSWORD}).status_code == 401
    # A token issued before deactivation stops working too.
    assert client.get("/users/me", headers=_auth(ok.json())).status_code == 401


# --- Company isolation -------------------------------------------------------


def test_a_company_never_sees_or_touches_another_companys_data(client, db_session):
    alpha = _signup(client)
    beta = _signup(client, company="Beta Distribution", email="patron@beta.example", name="Bruno")

    alpha_company = db_session.get(Company, uuid.UUID(alpha["company_id"]))
    supplier = Supplier(company_id=alpha_company.id, name="Fournisseur secret d'Alpha")
    customer = Customer(company_id=alpha_company.id, name="Client d'Alpha", status="active")
    db_session.add_all([supplier, customer])
    db_session.commit()

    # Alpha sees its own data.
    assert [s["name"] for s in client.get("/suppliers", headers=_auth(alpha)).json()] == ["Fournisseur secret d'Alpha"]
    assert client.get(f"/suppliers/{supplier.id}", headers=_auth(alpha)).status_code == 200

    # Beta sees nothing of it, even with the exact ids.
    assert client.get("/suppliers", headers=_auth(beta)).json() == []
    assert client.get("/customers", headers=_auth(beta)).json() == []
    assert client.get(f"/suppliers/{supplier.id}", headers=_auth(beta)).status_code == 404
    assert client.get(f"/objects/supplier/{supplier.id}/context", headers=_auth(beta)).status_code == 404
    assert client.get("/company", headers=_auth(beta)).json()["name"] == "Beta Distribution"
    assert "Alpha" in client.get("/objects/search", params={"q": "secret"}, headers=_auth(alpha)).text
    search = client.get("/objects/search", params={"q": "secret"}, headers=_auth(beta))
    assert search.status_code == 200 and "Alpha" not in search.text

    # ... and cannot change Alpha's company or Alpha's people.
    client.patch("/company", json={"name": "Piraté"}, headers=_auth(beta))
    db_session.expire_all()
    assert db_session.get(Company, alpha_company.id).name == "Négoce Alpha"
    res = client.patch(f"/users/{alpha['profile_id']}", json={"name": "Piraté"}, headers=_auth(beta))
    assert res.status_code == 404
    assert [u["name"] for u in client.get("/users", headers=_auth(beta)).json()] == ["Bruno"]


def test_a_scoped_session_refuses_to_write_for_another_company(session_factory, db_session):
    a = Company(name="A")
    b = Company(name="B")
    db_session.add_all([a, b])
    db_session.commit()

    scoped = session_factory()
    scope_session(scoped, a.id)
    scoped.add(Supplier(company_id=b.id, name="Intrus"))
    with pytest.raises(CrossTenantWriteError):
        scoped.flush()
    scoped.rollback()
    scoped.close()


# --- Team, invitations and company-defined roles ----------------------------


def test_director_invites_a_colleague_who_then_signs_in(client):
    director = _signup(client)
    created = client.post(
        "/users",
        json={"name": "Clara Compta", "email": "Clara@Alpha.example", "role": "accountant", "job_title": "Comptable"},
        headers=_auth(director),
    )
    assert created.status_code == 200, created.text
    clara = created.json()
    assert clara["email"] == "clara@alpha.example"
    assert clara["account_status"] == "no_access"

    invite = client.post(f"/users/{clara['id']}/invite", headers=_auth(director))
    assert invite.status_code == 200
    token = invite.json()["invite_url"].rsplit("/", 1)[1]

    seen = client.get(f"/auth/invitations/{token}")
    assert seen.status_code == 200
    assert seen.json()["company_name"] == "Négoce Alpha"
    assert seen.json()["job_title"] == "Comptable"

    accepted = client.post(f"/auth/invitations/{token}/accept", json={"password": PASSWORD})
    assert accepted.status_code == 200
    me = client.get("/users/me", headers=_auth(accepted.json())).json()
    assert me["role"] == "accountant"
    assert "view:finance" in me["permissions"]
    assert "view:treasury" not in me["permissions"]  # sensitive: the director grants it

    # The link is single-use, and she now signs in with her password.
    assert client.post(f"/auth/invitations/{token}/accept", json={"password": PASSWORD}).status_code == 404
    assert client.post("/auth/login", json={"email": "clara@alpha.example", "password": PASSWORD}).status_code == 200
    # Only someone with write:settings may invite.
    assert client.post(f"/users/{director['profile_id']}/invite", headers=_auth(accepted.json())).status_code == 403


def test_director_creates_a_company_role_and_assigns_it(client):
    director = _signup(client)
    role = client.post(
        "/users/custom-roles",
        json={
            "name": "Responsable logistique",
            "base_role": "operations",
            "access_grants": ["view:finance"],
            "access_revokes": ["action:submit_email"],
        },
        headers=_auth(director),
    )
    assert role.status_code == 201, role.text
    role = role.json()
    assert "view:finance" in role["permissions"]
    assert "action:submit_email" not in role["permissions"]

    person = client.post(
        "/users",
        json={"name": "Léo", "email": "leo@alpha.example", "custom_role_id": role["id"], "job_title": "Logisticien"},
        headers=_auth(director),
    ).json()
    assert person["role"] == "operations"
    assert person["custom_role_name"] == "Responsable logistique"
    assert "view:finance" in person["permissions"]

    # Per-person changes stack on top of the role.
    person = client.patch(f"/users/{person['id']}", json={"access_revokes": ["view:finance"]}, headers=_auth(director)).json()
    assert "view:finance" not in person["permissions"]

    # Changing the role changes everyone holding it.
    client.patch(f"/users/custom-roles/{role['id']}", json={"access_grants": ["view:finance", "view:sales"]}, headers=_auth(director))
    people = {u["name"]: u for u in client.get("/users", headers=_auth(director)).json()}
    assert "view:sales" in people["Léo"]["permissions"]

    # A role still held cannot be deleted.
    assert client.delete(f"/users/custom-roles/{role['id']}", headers=_auth(director)).status_code == 409


def test_company_roles_are_private_to_their_company(client):
    alpha = _signup(client)
    beta = _signup(client, company="Beta", email="patron@beta.example", name="Bruno")
    role = client.post("/users/custom-roles", json={"name": "ADV", "base_role": "sales"}, headers=_auth(alpha)).json()
    assert client.get("/users/custom-roles", headers=_auth(beta)).json() == []
    assert client.patch(f"/users/custom-roles/{role['id']}", json={"name": "x"}, headers=_auth(beta)).status_code == 404
    res = client.post("/users", json={"name": "Z", "custom_role_id": role["id"]}, headers=_auth(beta))
    assert res.status_code == 404


# --- Event Log isolation -----------------------------------------------------


def test_events_are_logged_for_the_company_that_published_them(session_factory, db_session):
    from app.core.entities import EventLogEntry
    from app.core.events.business_event import BusinessEvent
    from app.core.events.tenant import TenantEventBus
    from app.event_bus import build_event_bus

    a = Company(name="A")
    b = Company(name="B")
    db_session.add_all([a, b])
    db_session.commit()
    bus = build_event_bus(session_factory)

    # No subject and two companies: only the publishing request can tell.
    TenantEventBus(bus, a.id).publish(BusinessEvent(event_type="SomethingHappened", source="test", payload={}))
    bus.publish(BusinessEvent(event_type="SomethingElse", source="test", payload={}))

    logged = {e.event_type: e.company_id for e in db_session.query(EventLogEntry).all()}
    assert logged == {"SomethingHappened": a.id, "SomethingElse": None}


def test_one_companys_activity_never_shows_in_anothers_home(client):
    from app.access.deps import get_current_user
    from app.core.events.tenant import TenantEventBus
    from app.dependencies import get_event_bus
    from app.main import app
    from fastapi import Depends

    # Wire the bus exactly as production does (api_client replaces it).
    shared = app.dependency_overrides[get_event_bus]()
    app.dependency_overrides[get_event_bus] = lambda user=Depends(get_current_user): TenantEventBus(shared, user.profile.company_id)

    alpha = _signup(client)
    beta = _signup(client, company="Beta", email="patron@beta.example", name="Bruno")
    created = client.post("/actions/tasks", json={"title": "Relancer le fournisseur Zeta"}, headers=_auth(alpha))
    assert created.status_code in (200, 201), created.text

    assert "Zeta" in client.get("/home/activity", headers=_auth(alpha)).text
    assert "Zeta" not in client.get("/home/activity", headers=_auth(beta)).text
    assert "Zeta" not in client.get("/home", headers=_auth(beta)).text
    assert client.get("/actions/tasks", headers=_auth(beta)).json() == []
