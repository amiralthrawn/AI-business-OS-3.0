"""V3: the Veilleur (Perplexity), autonomy levels, the completion guide."""

import json

import pytest

from app.agents import perplexity
from app.config import get_settings
from tests.v2_support import api_client

PASSWORD = "correct horse battery"

FOUND = json.dumps([
    {"category": "événement", "title": "Salon Electronica Paris", "summary": "Salon professionnel des composants.", "why_it_matters": "Vos fournisseurs y exposent.",
     "date": "2099-11-12", "suggested_action": {"type": "calendar_event", "text": "Réserver la visite"}, "needs_info": None},
    {"category": "réputation", "title": "Note Google Maps de 3,4", "summary": "Note inférieure à vos concurrents.", "why_it_matters": "Impacte la confiance.",
     "date": None, "suggested_action": {"type": "task", "text": "Demander des avis aux clients satisfaits"}, "needs_info": "Quelle est l'adresse de votre agence principale ?"},
])


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


def test_without_a_key_the_veilleur_finds_nothing_and_says_so(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", None)
    headers = _director(client)
    res = client.post("/agents/veilleur/run", headers=headers).json()
    assert res["status"] == "not_configured" and res["found"] == 0
    overview = client.get("/agents/overview", headers=headers).json()
    assert overview["proposals"] == []
    veilleur = next(a for a in overview["agents"] if a["key"] == "veilleur")
    assert veilleur["configured"] is False


def test_findings_become_proposals_and_need_a_validation_by_default(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: (FOUND, ["https://example.org/electronica"]))
    headers = _director(client)
    res = client.post("/agents/veilleur/run", headers=headers).json()
    assert res["status"] == "ok" and res["found"] == 2  # same two items for both passes, deduplicated
    overview = client.get("/agents/overview", headers=headers).json()
    kinds = sorted((p["kind"], p["status"]) for p in overview["proposals"])
    assert kinds == [("finding", "new"), ("finding", "new"), ("missing_info", "new")]
    salon = next(p for p in overview["proposals"] if p["title"] == "Salon Electronica Paris")
    assert salon["sources"] == ["https://example.org/electronica"]
    # nothing in the calendar until the person accepts
    cal = client.get("/calendar", headers=headers, params={"start": "2099-11-01T00:00:00Z", "end": "2099-12-01T00:00:00Z"}).json()
    assert cal["events"] == []
    assert client.post(f"/agents/proposals/{salon['id']}/accept", headers=headers).status_code == 200
    cal = client.get("/calendar", headers=headers, params={"start": "2099-11-01T00:00:00Z", "end": "2099-12-01T00:00:00Z"}).json()
    assert [(e["title"], e["source"]) for e in cal["events"]] == [("Salon Electronica Paris", "veilleur")]
    # running again does not duplicate
    assert client.post("/agents/veilleur/run", headers=headers).json()["found"] == 0


def test_in_auto_mode_the_agent_acts_and_the_person_can_undo(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: (FOUND, []))
    headers = _director(client)
    assert client.put("/agents/settings", headers=headers, json={"enabled": True, "autonomy": {"calendar_event": "auto"}}).json()["autonomy"] == {"calendar_event": "auto", "task": "ask"}
    client.post("/agents/veilleur/run", headers=headers)
    window = {"start": "2099-11-01T00:00:00Z", "end": "2099-12-01T00:00:00Z"}
    assert len(client.get("/calendar", headers=headers, params=window).json()["events"]) == 1
    done = next(p for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["status"] == "auto_done")
    assert client.post(f"/agents/proposals/{done['id']}/undo", headers=headers).json()["status"] == "undone"
    assert client.get("/calendar", headers=headers, params=window).json()["events"] == []


def test_a_missing_info_question_is_answered_and_kept(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: (FOUND, []))
    headers = _director(client)
    client.post("/agents/veilleur/run", headers=headers)
    question = next(p for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["kind"] == "missing_info")
    assert client.post(f"/agents/proposals/{question['id']}/answer", headers=headers, json={"text": "12 rue Voltaire, Lyon"}).json()["status"] == "answered"
    plan = client.get("/configuration", headers=headers).json()
    assert "12 rue Voltaire" in json.dumps(plan)


def test_guide_percentage_grows_as_the_company_completes_the_product(client):
    headers = _director(client)
    first = client.get("/agents/overview", headers=headers).json()["guide"]
    client.post("/configuration/imports/auto", headers=headers, files={"file": ("clients.csv", b"Nom;Pays\nAcme;France\n")})
    second = client.get("/agents/overview", headers=headers).json()["guide"]
    assert second["percent"] > first["percent"]
    assert any("fournisseurs" in s["title"] for s in second["steps"])


def test_other_companies_never_see_these_proposals(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: (FOUND, []))
    headers = _director(client)
    client.post("/agents/veilleur/run", headers=headers)
    other = _director(client, company="Autre", email="o@autre.example")
    assert client.get("/agents/overview", headers=other).json()["proposals"] == []


def test_parse_items_tolerates_code_fences_and_noise():
    from app.agents import veilleur

    text = "Voici :\n```json\n[{\"title\": \"A\"}, {\"nope\": 1}]\n```"
    assert [i["title"] for i in veilleur.parse_items(text)] == ["A"]
    assert veilleur.parse_items("aucun résultat") == []
