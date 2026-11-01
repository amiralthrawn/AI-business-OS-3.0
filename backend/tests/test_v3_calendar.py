"""V3: the calendar -- AI events from real data, hand-written events, scoping."""

import pytest

from app.config import get_settings
from tests.v2_support import api_client

PASSWORD = "correct horse battery"
WINDOW = {"start": "2025-01-01T00:00:00Z", "end": "2025-03-01T00:00:00Z"}


@pytest.fixture(autouse=True)
def required_mode(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_mode", "required")


@pytest.fixture()
def client(session_factory):
    with api_client(session_factory) as c:
        yield c


def _director(client, company="Électro Négoce", email="d@electro.example"):
    res = client.post("/auth/signup", json={"company_name": company, "name": "Dir", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_calendar_is_filled_from_imported_data_and_classified(client):
    headers = _director(client)
    sales = "Date;Client;Montant\n2025-01-05;Acme SA;1000\n2025-01-05;Beta;500\n2025-02-01;Acme SA;300\n".encode()
    purchases = "Date;Fournisseur;Montant\n2025-01-10;Texas Chips;400\n".encode()
    client.post("/configuration/imports/auto", headers=headers, files={"file": ("ventes.csv", sales)})
    client.post("/configuration/imports/auto", headers=headers, files={"file": ("achats.csv", purchases)})
    body = client.get("/calendar", headers=headers, params=WINDOW).json()
    by_kind = {}
    for e in body["events"]:
        by_kind.setdefault(e["kind"], []).append(e)
    assert [e["count"] for e in by_kind["sale"]] == [2, 1]  # grouped per day
    assert by_kind["sale"][0]["amount"] == 1500.0 and by_kind["sale"][0]["period"] == "past"
    assert by_kind["purchase"][0]["amount"] == 400.0
    assert body["kinds"]["sale"]["group"] == "money"


def test_manual_events_can_be_added_changed_and_removed(client):
    headers = _director(client)
    res = client.post("/calendar/events", headers=headers, json={"title": "Salon Electronica", "kind": "trade_show", "starts_at": "2025-02-10T00:00:00Z"})
    assert res.status_code == 201
    event_id = res.json()["id"]
    events = client.get("/calendar", headers=headers, params=WINDOW).json()["events"]
    assert [(e["title"], e["kind"], e["source"]) for e in events] == [("Salon Electronica", "trade_show", "manual")]
    other = _director(client, company="Autre", email="o@autre.example")
    assert client.get("/calendar", headers=other, params=WINDOW).json()["events"] == []
    assert client.delete(f"/calendar/events/{event_id}", headers=other).status_code == 404
    assert client.put(f"/calendar/events/{event_id}", headers=headers, json={"title": "Electronica 2025", "kind": "weird", "starts_at": "2025-02-11T00:00:00Z"}).status_code == 200
    assert client.get("/calendar", headers=headers, params=WINDOW).json()["events"][0]["kind"] == "other"
    assert client.delete(f"/calendar/events/{event_id}", headers=headers).status_code == 204


def test_period_is_bounded(client):
    headers = _director(client)
    res = client.get("/calendar", headers=headers, params={"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"})
    assert res.status_code == 422
