"""Access reserved to the accounts in ALLOWED_LOGIN_EMAILS, sign-up closed."""

import pytest

from app.config import Settings, get_settings
from tests.v2_support import api_client

PASSWORD = "correct horse battery"
OWNER = "enzo.lusapro@gmail.com"


@pytest.fixture(autouse=True)
def required_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "required")


@pytest.fixture()
def client(session_factory):
    with api_client(session_factory) as c:
        yield c


def _signup(client, email):
    return client.post("/auth/signup", json={"company_name": "Co", "name": "N", "email": email, "password": PASSWORD})


def _lock(monkeypatch, signup=False):
    monkeypatch.setattr(get_settings(), "allowed_login_emails", "enzo.lusapro@gmail.com, Enzo92k@gmail.com")
    monkeypatch.setattr(get_settings(), "signup_enabled", signup)


def test_defaults_close_sign_up_and_list_only_the_two_owner_accounts(monkeypatch):
    monkeypatch.delenv("SIGNUP_ENABLED", raising=False)
    monkeypatch.delenv("ALLOWED_LOGIN_EMAILS", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.signup_enabled is False
    assert defaults.login_allowed("enzo.lusapro@gmail.com")
    assert defaults.login_allowed(" ENZO92K@gmail.com ")
    assert not defaults.login_allowed("someone@else.example")
    assert not defaults.login_allowed(None)


def test_sign_up_is_closed(client, monkeypatch):
    _lock(monkeypatch)
    assert _signup(client, OWNER).status_code == 403


def test_other_accounts_cannot_sign_in_and_lose_their_open_sessions(client, monkeypatch):
    stranger = _signup(client, "stranger@else.example").json()
    owner = _signup(client, OWNER).json()
    _lock(monkeypatch)

    assert client.post("/auth/login", json={"email": "stranger@else.example", "password": PASSWORD}).status_code == 403
    assert client.get("/users/me", headers={"Authorization": f"Bearer {stranger['access_token']}"}).status_code == 401

    assert client.post("/auth/login", json={"email": "Enzo.Lusapro@gmail.com", "password": PASSWORD}).status_code == 200
    assert client.get("/users/me", headers={"Authorization": f"Bearer {owner['access_token']}"}).status_code == 200


def test_sign_up_stays_reserved_even_when_reopened(client, monkeypatch):
    _lock(monkeypatch, signup=True)
    assert _signup(client, "stranger@else.example").status_code == 403
    assert _signup(client, "enzo92k@gmail.com").status_code == 201
