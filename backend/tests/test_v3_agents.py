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
    assert client.put("/agents/settings", headers=headers, json={"enabled": True, "autonomy": {"calendar_event": "auto"}}).json()["autonomy"] == {"calendar_event": "auto", "task": "ask", "browser": "ask", "execute": "ask"}
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


def test_perplexity_agent_api_response_is_parsed(monkeypatch):
    import httpx

    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, body=json)
        payload = {"output": [
            {"type": "search_results", "results": [{"id": 1, "url": "https://a.example/x"}, {"id": 2, "url": "https://b.example/y"}]},
            {"type": "message", "content": [{"type": "output_text", "text": "Réponse utile[1][2]."}]},
        ]}
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    text, sources = perplexity.ask("sys", "question")
    assert text == "Réponse utile." and sources == ["https://a.example/x", "https://b.example/y"]
    assert seen["url"].endswith("/v1/agent") and seen["body"]["instructions"] == "sys" and seen["body"]["effort"] == "fast"


def test_gemini_is_used_first_and_its_citations_are_parsed(monkeypatch):
    import httpx

    monkeypatch.setattr(get_settings(), "gemini_api_key", "g")
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "p")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json)
        payload = {"steps": [
            {"type": "google_search_call", "arguments": {"queries": ["x"]}},
            {"type": "model_output", "content": [{"type": "text", "text": "Voici.", "annotations": [
                {"type": "url_citation", "url": "https://doc.example/a", "title": "doc.example"}]}]},
        ]}
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    text, sources = perplexity.ask("sys", "q")
    assert (text, sources) == ("Voici.", ["https://doc.example/a"])
    assert "generativelanguage" in seen["url"] and seen["headers"]["x-goog-api-key"] == "g"
    assert seen["body"]["tools"] == [{"type": "google_search"}]


def test_openrouter_is_used_first_with_sonar_citations(monkeypatch):
    import httpx

    monkeypatch.setattr(get_settings(), "openrouter_api_key", "o")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "g")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, body=json)
        payload = {"citations": ["https://a.example/1"], "choices": [{"message": {"content": "Oui[1].", "annotations": [
            {"type": "url_citation", "url_citation": {"url": "https://b.example/2", "title": "b"}}]}}]}
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    text, sources = perplexity.ask("sys", "q")
    assert text == "Oui." and sources == ["https://a.example/1", "https://b.example/2"]
    assert "openrouter.ai" in seen["url"] and seen["body"]["model"] == "perplexity/sonar"


def test_watch_topics_are_saved_and_given_to_the_veilleur(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "perplexity_api_key", "k")
    prompts = []

    def fake_ask(system, user, **kw):
        prompts.append(user)
        return "[]", []

    monkeypatch.setattr(perplexity, "ask", fake_ask)
    headers = _director(client)
    res = client.put("/agents/watch-topics", headers=headers, json={"topics": ["oemstrade.com : prix", "oemstrade.com : prix", "Salon Electronica Munich"], "run": True})
    assert res.status_code == 200, res.text
    assert res.json()["topics"] == ["oemstrade.com : prix", "Salon Electronica Munich"]
    assert any("oemstrade.com : prix" in p and "EXPRESSÉMENT" in p for p in prompts)
    overview = client.get("/agents/overview", headers=headers).json()
    assert overview["settings"]["watch_topics"] == ["oemstrade.com : prix", "Salon Electronica Munich"]
    # changing the autonomy settings keeps the topics
    client.put("/agents/settings", headers=headers, json={"enabled": True, "autonomy": {"task": "auto"}})
    assert client.get("/agents/overview", headers=headers).json()["settings"]["watch_topics"] == ["oemstrade.com : prix", "Salon Electronica Munich"]


def test_agents_overview_shows_models_runs_and_model_requests(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "o")
    monkeypatch.setattr("app.agents.veilleur_agent.enabled", lambda: False)  # the plain topic search path
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: ('[{"category": "événement", "title": "Electronica Munich", "summary": "Salon.", "why_it_matters": "Fournisseurs.", "date": null}]', ["https://s.example/e"]))
    headers = _director(client)
    ask = client.post("/agents/veilleur/ask", headers=headers, json={"request": "Salon Electronica Munich : exposants", "follow": True})
    assert ask.status_code == 200 and ask.json()["status"] == "ok" and ask.json()["found"][0]["title"] == "Electronica Munich"
    overview = client.get("/agents/overview", headers=headers).json()
    agents = {a["key"]: a for a in overview["agents"]}
    assert set(agents) == {"veilleur", "analyste", "guide", "executant", "navigateur"}
    assert agents["veilleur"]["model"]["provider"] == "OpenRouter" and agents["analyste"]["model"]["kind"] == "rules"
    assert agents["veilleur"]["recent_runs"][0]["message"].startswith("1 résultat")
    assert overview["settings"]["watch_topics"] == ["Salon Electronica Munich : exposants"]
    req = client.post("/agents/model-requests", headers=headers, json={"agent": "veilleur", "wanted": "Perplexity Sonar Pro", "reason": "résultats trop légers"})
    assert req.status_code == 201 and req.json()["status"] == "requested"
    assert client.get("/agents/overview", headers=headers).json()["model_requests"][0]["wanted"] == "Perplexity Sonar Pro"
    assert client.post("/agents/model-requests", headers=headers, json={"agent": "nope", "wanted": "x1"}).status_code == 404


def test_the_assistant_redirects_web_requests_to_the_veilleur(client):
    headers = _director(client)
    res = client.post("/ai/ask", headers=headers, json={"question": "Surveille oemstrade.com et le salon Electronica à Munich"})
    assert res.status_code == 200 and "Veilleur" in res.json()["answer"] and res.json()["agent"] == "assistant"


def test_usage_is_booked_per_agent_and_priced(client):
    from app.agents import perplexity, service

    headers = _director(client)

    perplexity.drain_usage()
    perplexity._record("perplexity/sonar", {"prompt_tokens": 1000, "completion_tokens": 500})
    perplexity._record("perplexity/sonar", {"prompt_tokens": 100, "completion_tokens": 100, "cost": 0.01})
    entries = perplexity.drain_usage()
    assert len(entries) == 2 and perplexity.drain_usage() == []
    assert abs(service._cost(entries[0]) - (0.0015 + 0.005)) < 1e-9
    assert service._cost(entries[1]) == 0.01
    overview = client.get("/agents/overview", headers=headers).json()
    assert overview["usage"]["total"]["tokens"] == 0
    assert overview["usage"]["catalog"][0]["model"] == "gemini-3.5-flash-lite"


def test_veilleur_is_an_agent_that_reads_asks_the_analyste_and_saves(client, monkeypatch):
    from app.agents import perplexity, veilleur_agent

    headers = _director(client, "Agent Co", "agent@co.example")
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    monkeypatch.setattr(veilleur_agent, "read_page", lambda url: ("Prix STM32F4 : 7,90 € chez OEMsTrade " * 20, url))
    script = iter([
        {"content": "", "tool_calls": [{"id": "1", "function": {"name": "ask_analyste", "arguments": '{"terms": ["STM32"]}'}}]},
        {"content": "", "tool_calls": [{"id": "2", "function": {"name": "read_page", "arguments": '{"url": "https://www.oemstrade.com/x"}'}}]},
        {"content": "", "tool_calls": [{"id": "3", "function": {"name": "save_finding", "arguments": '{"title": "Prix STM32F4 chez OEMsTrade", "summary": "7,90 €", "why_it_matters": "Comparer à votre coût", "sources": ["https://www.oemstrade.com/x", "https://invented.example"]}'}}]},
        {"content": "J'ai enregistré le prix du STM32F4."},
    ])
    seen_tools = []
    def fake_chat(messages):
        seen_tools.append([m for m in messages if m["role"] == "tool"][-1]["content"] if any(m["role"] == "tool" for m in messages) else None)
        return next(script)
    monkeypatch.setattr(veilleur_agent, "_chat", fake_chat)
    res = client.post("/agents/veilleur/ask", headers=headers, json={"request": "Compare mes prix avec OEMsTrade " * 30, "follow": False}).json()
    assert res["status"] == "ok" and res["message"].startswith("J'ai enregistré")
    assert len(res["found"]) == 1 and res["found"][0]["sources"] == ["https://www.oemstrade.com/x"]  # the invented source is dropped
    assert seen_tools[1].startswith("## Vue d'ensemble")  # the Analyste answered from the company data
    props = client.get("/agents/overview", headers=headers).json()["proposals"]
    assert any(p["title"] == "Prix STM32F4 chez OEMsTrade" for p in props)


def test_read_page_refuses_private_addresses():
    from app.agents import veilleur_agent

    text, url = veilleur_agent.read_page("http://127.0.0.1:8000/secret")
    assert url is None and "publique" in text


def test_analyste_tells_what_changed_since_the_last_analysis(client):
    headers = _director(client, "Ana Co", "ana@co.example")
    first = client.post("/agents/analyste/run", headers=headers).json()
    assert first["changed"] is True and first["summary"].startswith("Première analyse")
    second = client.post("/agents/analyste/run", headers=headers).json()
    assert second["changed"] is False and "Rien n'a changé" in second["summary"]
    client.post("/catalog/products", headers=headers, json={"name": "Nouveau", "sku": "N1"})
    third = client.post("/agents/analyste/run", headers=headers).json()
    assert third["changed"] is True and "produit" in third["summary"]


def test_context_from_the_analyste_reaches_the_veilleur(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client, "Ctx Co", "ctx@co.example")
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    seen = {}
    def fake_run(session, company, profile, request, save):
        seen["request"] = request
        return {"answer": "ok", "found": []}
    monkeypatch.setattr(veilleur_agent, "run", fake_run)
    res = client.post("/agents/veilleur/ask", headers=headers, json={"request": "Creuse ce point", "follow": False, "context": "Marge en baisse sur STM32"}).json()
    assert res["status"] == "ok" and "Marge en baisse sur STM32" in seen["request"] and "Creuse ce point" in seen["request"]


def test_agents_remember_their_exchanges_and_the_client_can_clear_them(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client, "Mem Co", "mem@co.example")
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    profiles = []
    def fake_run(session, company, profile, request, save):
        profiles.append(profile)
        return {"answer": "Prix relevés chez OEMsTrade.", "found": [{"title": "Prix STM32", "summary": "", "why": "", "sources": []}]}
    monkeypatch.setattr(veilleur_agent, "run", fake_run)
    client.post("/agents/veilleur/ask", headers=headers, json={"request": "Compare OEMsTrade", "follow": False})
    client.post("/agents/veilleur/ask", headers=headers, json={"request": "Et Accuris ?", "follow": False})
    assert "Mémoire" not in profiles[0] and "Compare OEMsTrade" in profiles[1] and "Prix STM32" in profiles[1]
    client.post("/agents/analyste/run", headers=headers)
    agents = {a["key"]: a for a in client.get("/agents/overview", headers=headers).json()["agents"]}
    assert agents["veilleur"]["memory_count"] == 2 and agents["analyste"]["memory_count"] == 1
    assert client.delete("/agents/memory/veilleur", headers=headers).status_code == 204
    agents = {a["key"]: a for a in client.get("/agents/overview", headers=headers).json()["agents"]}
    assert agents["veilleur"]["memory_count"] == 0


def test_full_analysis_is_handed_to_the_veilleur(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client, "Dos Co", "dos@co.example")
    client.post("/catalog/products", headers=headers, json={"name": "Microcontrôleur STM32F4", "sku": "STM32F4"})
    client.post("/agents/analyste/run", headers=headers)
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    seen = {}
    monkeypatch.setattr(veilleur_agent, "run", lambda session, company, profile, request, save: seen.update(request=request) or {"answer": "ok", "found": []})
    res = client.post("/agents/veilleur/ask", headers=headers, json={"request": "Compare les prix du STM32F4", "follow": False, "with_analysis": True}).json()
    assert res["shared_chars"] > 200
    for part in ("## Vue d'ensemble", "## Risques détectés", "## Éléments de vos données liés à la demande", "STM32F4", "Résumé de la dernière analyse"):
        assert part in seen["request"]


def test_site_is_read_understood_shared_and_turned_into_proposals(client, monkeypatch):
    from app.website import intelligence

    headers = _director(client, "Site Co", "site@co.example")
    guide = client.get("/agents/overview", headers=headers).json()["guide"]
    assert any("site web" in s["title"].lower() for s in guide["steps"])
    assert client.patch("/company", headers=headers, json={"website_url": "pas un site"}).status_code == 400
    assert client.patch("/company", headers=headers, json={"website_url": "www.fe-components.fr"}).json()["website_url"] == "https://www.fe-components.fr"
    site = {"url": "https://www.fe-components.fr/", "emails": ["contact@fe-components.fr"], "phones": [], "social": [], "schema": [],
            "pages": [{"url": "https://www.fe-components.fr/", "title": "FE Components", "description": "Négoce de composants", "headings": ["Condensateurs"], "text": "Nous négocions des composants.", "words": 5}]}
    monkeypatch.setattr(intelligence, "crawl", lambda url: site)
    monkeypatch.setattr(intelligence, "understand", lambda name, s: ({"summary": "Négociant en composants électroniques.", "offer": ["Condensateurs", "Microcontrôleurs"], "audience": "Industriels", "strengths": [], "weaknesses": ["Pas de prix"],
                                                                      "improvements": [{"title": "Ajouter un formulaire de devis", "why": "Plus de demandes", "action": "Créer le formulaire"}], "syncs": [{"title": "Catalogue vers le site", "why": "Prix à jour"}]}, True))
    res = client.post("/website/integrate", headers=headers, json={}).json()
    assert res["created"] == 3 and res["not_in_catalog"] == ["Condensateurs", "Microcontrôleurs"]
    overview = client.get("/agents/overview", headers=headers).json()
    titles = [p["title"] for p in overview["proposals"]]
    assert "Site web : Ajouter un formulaire de devis" in titles and any(p["agent"] == "analyste" for p in overview["proposals"])
    assert not any("Ajouter le site web" in s["title"] or "Faire analyser" in s["title"] for s in overview["guide"]["steps"])
    state = client.get("/website", headers=headers).json()
    assert state["intelligence"]["analysis"]["summary"].startswith("Négociant")


def test_a_company_without_site_can_ask_for_one(client):
    headers = _director(client, "Nosite Co", "nosite@co.example")
    assert client.post("/website/creation-request", headers=headers, json={"notes": "Vitrine + catalogue"}).status_code == 201
    state = client.get("/website", headers=headers).json()
    assert state["intelligence"]["request"]["status"] == "requested"
    guide = client.get("/agents/overview", headers=headers).json()["guide"]
    assert not any("Ajouter le site web" in s["title"] for s in guide["steps"])


def test_blocked_site_falls_back_to_a_sourced_web_search(client, monkeypatch):
    from app.agents import perplexity
    from app.website import intelligence

    headers = _director(client, "Block Co", "block@co.example")
    client.patch("/company", headers=headers, json={"website_url": "fecomponents.shop"})
    def blocked(url):
        raise intelligence.SiteError("Impossible de lire le site (https://fecomponents.shop/ : HTTP 403).", blocked=True)
    monkeypatch.setattr(intelligence, "crawl", blocked)
    monkeypatch.setattr(perplexity, "configured", lambda: True)
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: ("FE Components vend des composants électroniques en ligne.", ["https://example.org/fe"]))
    res = client.post("/website/integrate", headers=headers, json={}).json()
    assert res["indirect"] is True and res["pages"] == 1
    monkeypatch.setattr(perplexity, "ask", lambda system, user, **kw: ("NON_TROUVE", []))
    again = client.post("/website/integrate", headers=headers, json={})
    assert again.status_code == 400 and "bloque" in again.json()["detail"]


def test_executant_does_the_task_records_it_and_it_can_be_undone(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client, "Exec Co", "exec@co.example")
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    script = iter([
        {"content": "", "tool_calls": [{"id": "1", "function": {"name": "create_supplier", "arguments": '{"name": "Acme Parts", "country": "Allemagne"}'}}]},
        {"content": "", "tool_calls": [{"id": "2", "function": {"name": "create_product", "arguments": '{"name": "Condensateur 10uF", "sku": "C10"}'}},
                                       {"id": "3", "function": {"name": "create_calendar_event", "arguments": '{"title": "Electronica", "date": "2026-11-10"}'}},
                                       {"id": "4", "function": {"name": "draft_email", "arguments": '{"to": "sales@acme.example", "subject": "Prix C10", "body": "Bonjour"}'}}]},
        {"content": "J'ai créé le fournisseur, le produit, l'événement et un brouillon."},
    ])
    monkeypatch.setattr(veilleur_agent, "_chat", lambda messages, tools=None: next(script))
    res = client.post("/agents/executant/ask", headers=headers, json={"request": "Ajoute Acme Parts et le condensateur C10"}).json()
    assert res["status"] == "ok" and len(res["done"]) == 4 and "brouillon" in res["message"]
    assert client.get("/catalog/products", headers=headers).json()
    overview = client.get("/agents/overview", headers=headers).json()
    card = next(p for p in overview["proposals"] if p["agent"] == "executant")
    assert card["status"] == "auto_done"
    assert client.post(f"/agents/proposals/{card['id']}/undo", headers=headers).json()["status"] == "undone"
    assert client.get("/catalog/products", headers=headers).json() == []
    assert any(a["key"] == "executant" for a in overview["agents"])


def test_a_task_proposal_can_be_done_by_the_executant(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client, "Exec2 Co", "exec2@co.example")
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "k")
    monkeypatch.setattr(veilleur_agent, "run", lambda session, company, profile, request, save: save({"title": "Ajouter la référence STM32F4", "summary": "À créer", "why_it_matters": "Suivre la marge", "suggested_action": {"type": "task", "text": "Ajouter STM32F4"}}, ["https://s.example"]) and {"answer": "ok", "found": []})
    client.post("/agents/veilleur/ask", headers=headers, json={"request": "Cherche des références", "follow": False})
    proposal = next(p for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["title"] == "Ajouter la référence STM32F4")
    script = iter([{"content": "", "tool_calls": [{"id": "1", "function": {"name": "create_product", "arguments": '{"name": "STM32F4", "sku": "STM32F4"}'}}]}, {"content": "Référence ajoutée."}])
    monkeypatch.setattr(veilleur_agent, "_chat", lambda messages, tools=None: next(script))
    res = client.post(f"/agents/proposals/{proposal['id']}/execute", headers=headers).json()
    assert res["status"] == "accepted" and res["done"][0]["kind"] == "product"


def test_mail_and_site_control_are_asked_until_done_and_count_in_the_percentage(client):
    headers = _director(client, "Conn Co", "conn@co.example")
    before = client.get("/agents/overview", headers=headers).json()["guide"]
    hrefs = [s["href"] for s in before["steps"]]
    assert "/?service=mail" in hrefs and "/?service=site_control" in hrefs
    services = client.get("/configuration/services", headers=headers).json()
    assert {s["service"] for s in services} == {"mail", "site_control"} and all(s["state"] == "none" for s in services)
    assert client.post("/configuration/services/mail", headers=headers, json={"tool_key": "wordpress"}).status_code == 404
    assert client.post("/configuration/services/mail", headers=headers, json={"tool_key": "gmail"}).json()["state"] == "requested"
    assert client.post("/configuration/services/site_control", headers=headers, json={"tool_key": "shopify"}).status_code == 201
    after = client.get("/agents/overview", headers=headers).json()["guide"]
    assert after["percent"] > before["percent"]
    assert "/?service=mail" not in [s["href"] for s in after["steps"]]


def _wait_for(client, headers, task_id, wanted, seconds=40):
    import time

    end = time.time() + seconds
    while time.time() < end:
        data = client.get(f"/browser/tasks/{task_id}", headers=headers).json()
        if data["status"] in wanted:
            return data
        time.sleep(0.3)
    raise AssertionError(f"timeout, last: {data}")


def test_ai_browser_acts_hands_over_to_the_person_and_finishes(client, monkeypatch, tmp_path):
    import http.server
    import os
    import threading

    from app.agents import veilleur_agent
    from app.browser import manager

    exe = "/opt/pw-browsers/chromium-1243/chrome-linux64/chrome"
    if not os.path.exists(exe):
        pytest.skip("no local chromium")
    (tmp_path / "index.html").write_text("<html><body><h1>Portail</h1><button style='position:absolute;left:100px;top:100px;width:200px;height:60px' onclick=\"document.title='clicked'\">Valider</button><input id=i style='position:absolute;left:100px;top:300px'></body></html>")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/index.html"

    headers = _director(client, "Browse Co", "browse@co.example")
    s = get_settings()
    monkeypatch.setattr(s, "openrouter_api_key", "k")
    monkeypatch.setattr(s, "browser_local", True)
    monkeypatch.setattr(s, "browser_local_executable", exe)
    assert client.get("/browser/status", headers=headers).json()["available"] is True
    script = iter([
        {"name": "click", "args": {"x": 150, "y": 130, "why": "Valider"}},
        {"name": "ask_human", "args": {"reason": "Connectez-vous"}},
        {"name": "done", "args": {"summary": "Portail ouvert et validé.", "success": True}},
    ])
    monkeypatch.setattr(manager, "_decide", lambda task, shot, text: next(script))
    task = client.post("/browser/tasks", headers=headers, json={"goal": "Valider le portail", "start_url": url}).json()
    waiting = _wait_for(client, headers, task["id"], {"needs_human", "failed", "done"})
    assert waiting["status"] == "needs_human" and waiting["reason"] == "Connectez-vous"
    assert any("Clique" in st["text"] for st in waiting["steps"])
    assert client.get(f"/browser/tasks/{task['id']}/screen", headers=headers).headers["content-type"] == "image/jpeg"
    assert client.post(f"/browser/tasks/{task['id']}/input", headers=headers, json={"type": "type", "text": "motdepasse-secret"}).status_code == 200
    assert client.post(f"/browser/tasks/{task['id']}/hand-back", headers=headers).json()["status"] == "running"
    finished = _wait_for(client, headers, task["id"], {"done", "failed"})
    assert finished["status"] == "done" and "validé" in finished["summary"]
    assert "motdepasse-secret" not in str(finished)  # what the person types is never logged
    server.shutdown()


def test_gmail_oauth_connection_is_read_only_encrypted_and_ingests_mail(client, monkeypatch):
    from datetime import datetime, timezone
    from urllib.parse import parse_qs, urlparse

    from app.connectors import oauth
    from app.connectors.models import ExternalEmail

    headers = _director(client, "Oauth Co", "oauth@co.example")
    s = get_settings()
    assert client.get("/oauth/google/start", headers=headers).status_code == 400  # not enabled without credentials
    monkeypatch.setattr(s, "google_oauth_client_id", "cid")
    monkeypatch.setattr(s, "google_oauth_client_secret", "sec")
    url = client.get("/oauth/google/start", headers=headers).json()["url"]
    q = parse_qs(urlparse(url).query)
    assert "gmail.readonly" in q["scope"][0] and "send" not in q["scope"][0] and q["client_id"] == ["cid"]
    monkeypatch.setattr(oauth, "_token_call", lambda provider, data: {"refresh_token": "REFRESH-SECRET", "access_token": "acc"})
    class Fake:  # userinfo answer
        def json(self): return {"email": "boss@fe-components.fr"}
    monkeypatch.setattr(oauth.httpx, "get", lambda *a, **k: Fake())
    msg = ExternalEmail(external_id="g1", thread_id="t1", sender="client@acme.example", recipients=["boss@fe-components.fr"], subject="Demande de prix", body="Bonjour, prix du STM32 ?", timestamp=datetime.now(timezone.utc))
    monkeypatch.setattr(oauth, "fetch", lambda session, company_id, provider: [msg])
    res = client.get("/oauth/google/callback", params={"code": "abc", "state": q["state"][0]}, follow_redirects=False)
    assert res.status_code == 302 and "connected=gmail" in res.headers["location"]
    st = next(p for p in client.get("/oauth/status", headers=headers).json() if p["provider"] == "google")
    assert st["connected"] is True and st["account"] == "boss@fe-components.fr" and st["last_sync"]
    assert "REFRESH-SECRET" not in str(client.get("/configuration", headers=headers).json())
    assert "/?service=mail" not in [x["href"] for x in client.get("/agents/overview", headers=headers).json()["guide"]["steps"]]
    assert client.get("/oauth/google/callback", params={"code": "abc", "state": "forged"}, follow_redirects=False).headers["location"].find("oauth_error") > 0
    assert client.delete("/oauth/google", headers=headers).status_code == 204


def test_decisions_recommend_the_browser_and_it_can_run_alone(client, monkeypatch):
    from app.browser import manager

    headers = _director(client, "Nav Co", "nav@co.example")
    started = []
    monkeypatch.setattr(manager, "available", lambda: True)
    class T:  # stands for a started browser task
        id = "task42"
    monkeypatch.setattr(manager, "start", lambda company_id, goal, url=None: started.append((goal, url)) or T())
    assert client.put("/configuration", headers=headers, json={"sector_key": "electronics_trading", "tools": ["pennylane"]}).status_code == 200
    client.post("/agents/analyste/run", headers=headers)
    cards = [p for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["action_type"] == "browser"]
    assert len(cards) == 1 and "Pennylane" in cards[0]["title"] and cards[0]["agent"] == "guide"
    accepted = client.post(f"/agents/proposals/{cards[0]['id']}/accept", headers=headers).json()
    assert accepted["status"] == "accepted" and started and "Pennylane" in started[0][0]
    # autonomy: the next recommendation runs without being consulted
    client.put("/agents/settings", headers=headers, json={"enabled": True, "autonomy": {"browser": "auto"}})
    client.put("/configuration", headers=headers, json={"sector_key": "electronics_trading", "tools": ["pennylane", "sage_compta"]})
    client.post("/agents/analyste/run", headers=headers)
    assert len(started) == 2 and any(p["status"] == "auto_done" and p["action_type"] == "browser" for p in client.get("/agents/overview", headers=headers).json()["proposals"])


def test_an_unfinished_connection_comes_back_until_it_is_dismissed(client, db_session):
    from app.agents import followup
    from app.core.entities import Company

    headers = _director(client)
    company = db_session.query(Company).first()
    followup.track(db_session, company.id, "oauth:google", "Connexion de la messagerie", "in_progress", kind="connection")
    assert client.get("/agents/activity", headers=headers).json()["unfinished"] == []  # just started: not late yet
    followup.track(db_session, company.id, "tool:qonto", "Récupérer les données de Qonto", "stopped")
    data = client.get("/agents/activity", headers=headers).json()
    assert [i["key"] for i in data["unfinished"]] == ["tool:qonto"]
    assert {i["status"] for i in data["items"]} == {"in_progress", "stopped"}
    data = client.post("/agents/activity/dismiss", headers=headers, json={"key": "tool:qonto"}).json()
    assert data["unfinished"] == [] and [i["key"] for i in data["items"]] == ["oauth:google"]
    followup.track(db_session, company.id, "oauth:google", "Connexion de la messagerie", "done")
    assert client.get("/agents/activity", headers=headers).json()["items"][0]["status"] == "done"


def test_the_guide_asks_questions_and_deduces_tasks_from_the_answer(client, monkeypatch):
    from app.agents import veilleur_agent

    headers = _director(client)
    assert client.post("/agents/questions/refresh", headers=headers).json()["created"] >= 1
    questions = [p for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["kind"] == "missing_info"]
    assert questions and client.post("/agents/questions/refresh", headers=headers).json()["created"] == 0  # never asked twice
    monkeypatch.setattr(veilleur_agent, "enabled", lambda: True)
    monkeypatch.setattr(
        perplexity, "chat",
        lambda system, user, **kw: json.dumps({"tasks": [{"title": "Rassembler le FEC", "summary": "Demander le FEC au comptable", "action": "task", "text": "Demander le FEC"}], "follow_up": "Qui est votre comptable ?", "learned": "Le comptable détient le FEC"}),
    )
    res = client.post(f"/agents/proposals/{questions[0]['id']}/answer", headers=headers, json={"text": "Mon comptable a tout"}).json()
    assert res["deduced"]["tasks"] == 1 and res["deduced"]["follow_up"] == "Qui est votre comptable ?"
    overview = client.get("/agents/overview", headers=headers).json()
    assert any(p["title"] == "Rassembler le FEC" for p in overview["proposals"])
    assert any(p["title"] == "Qui est votre comptable ?" for p in overview["proposals"])
    guide = overview["guide"]
    assert any(s["import_kind"] == "fec" for s in guide["steps"]) or any(s["import_kind"] for s in guide["steps"])


def test_the_analysis_reports_where_it_is_and_can_be_stopped(client, db_session):
    from app.agents import progress
    from app.core.entities import Company

    headers = _director(client)
    client.post("/agents/analyste/run", headers=headers)
    jobs = client.get("/agents/progress", headers=headers).json()
    assert jobs[0]["agent"] == "analyste" and jobs[0]["status"] == "done" and jobs[0]["percent"] == 100
    assert len(jobs[0]["steps"]) >= 3  # it said what it was doing along the way
    company = db_session.query(Company).first()
    progress.start(company.id, "analyste", "Analyse des données")
    assert client.post("/agents/progress/analyste/cancel", headers=headers).json() == {"cancelled": True}
    with pytest.raises(progress.Cancelled):
        progress.step(company.id, "analyste", "encore", 10)


def test_zero_revenue_makes_the_analyste_ask_why(client):
    headers = _director(client)
    client.post("/agents/questions/refresh", headers=headers)
    titles = [p["title"] for p in client.get("/agents/overview", headers=headers).json()["proposals"] if p["kind"] == "missing_info"]
    assert any("à 0" in t for t in titles)
