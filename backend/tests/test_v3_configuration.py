"""V3: the configuration phase -- sector, tools, AI profile, real file imports."""

import io

import pytest
from openpyxl import Workbook

from app.configuration import sectors, tools
from app.config import get_settings
from app.core.entities import Customer, Product, Supplier
from tests.v2_support import api_client

PASSWORD = "correct horse battery"


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


def test_catalogue_is_large_consistent_and_covers_the_named_tools():
    keys = {k for k, _, _ in tools.TOOLS}
    assert len(keys) == len(tools.TOOLS) >= 150
    for named in ("sap_s4hana", "oracle_netsuite", "odoo", "salesforce", "pennylane", "power_bi", "excel", "azure", "qonto", "bnp_paribas", "attijariwafa"):
        assert named in keys
    assert all(cat in tools.CATEGORIES for _, _, cat in tools.TOOLS)
    assert all(group in sectors.GROUPS for _, _, group in sectors.SECTORS)
    assert len(sectors.SECTORS) >= 50 and "negoce_electronique" in {k for k, _, _ in sectors.SECTORS}


def test_configuration_drives_company_sector_functions_and_ai_profile(client):
    headers = _director(client)
    catalog = client.get("/configuration/catalog", headers=headers).json()
    assert {"sectors", "tools", "functions", "categories"} <= set(catalog)

    res = client.put(
        "/configuration",
        headers=headers,
        json={
            "sector_key": "negoce_electronique",
            "functions": ["finance", "sales", "hr", "marketing"],
            "tools": ["odoo", "pennylane", "qonto", "excel", "not_a_tool"],
            "custom_tools": ["Mon ERP maison"],
            "problems": "Marges qui fondent sur les composants",
            "objectives": "Sécuriser la marge",
            "company_size": "11–50",
            "country": "FR",
        },
    )
    assert res.status_code == 200, res.text
    profile = res.json()["ai_profile"]
    assert profile["group"] == "trading"
    assert "marge par référence" in profile["key_metrics"]
    assert {t["key"] for t in profile["tools"]} == {"odoo", "pennylane", "qonto", "excel"}
    assert profile["custom_tools"] == ["Mon ERP maison"]

    assert client.get("/company", headers=headers).json()["industry"].startswith("Négoce de composants")
    ctx = client.get("/business-context", headers=headers).json()
    assert ctx["monitored_domains"] == ["finance", "sales", "hr", "marketing"]

    plan = client.get("/configuration/integration-plan", headers=headers).json()["tools"]
    assert {p["key"] for p in plan} == {"odoo", "pennylane", "qonto", "excel"}
    assert all(p["status"] == "to_connect" for p in plan)


def test_other_sector_uses_the_companys_own_words(client):
    headers = _director(client)
    res = client.put("/configuration", headers=headers, json={"sector_key": "autre", "sector_custom": "Location de chapiteaux"})
    assert res.json()["ai_profile"]["group"] == "generic"
    assert client.get("/company", headers=headers).json()["industry"] == "Location de chapiteaux"


def test_only_users_who_may_edit_settings_can_configure(client):
    headers = _director(client)
    me = client.get("/users/me", headers=headers).json()
    assert me  # director can configure; an employee profile is refused below
    created = client.post("/users", headers=headers, json={"name": "Emma", "role": "employee", "email": "e@electro.example"})
    assert created.status_code in (200, 201), created.text
    invite = client.post(f"/users/{created.json()['id']}/invite", headers=headers).json()
    token = invite["invite_url"].rsplit("/", 1)[-1]
    session = client.post(f"/auth/invitations/{token}/accept", json={"password": PASSWORD}).json()
    emp = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.put("/configuration", headers=emp, json={"sector_key": "autre"}).status_code == 403
    assert client.post("/configuration/imports/customers", headers=emp, files={"file": ("c.csv", b"Nom\nX\n")}).status_code == 403


def test_customer_csv_import_is_real_idempotent_and_company_scoped(client, db_session):
    headers = _director(client)
    csv_bytes = "Client;Pays;Statut\nAcme SA;France;actif\nBeta GmbH;Allemagne;prospect\n;Suisse;actif\n".encode("cp1252")
    res = client.post("/configuration/imports/customers", headers=headers, files={"file": ("clients.csv", csv_bytes)}, params={"tool": "excel"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["created"], body["updated"], body["skipped"]) == (2, 0, 1)
    assert body["recognised_columns"]["name"] == "Client"

    again = client.post("/configuration/imports/customers", headers=headers, files={"file": ("clients.csv", csv_bytes)}).json()
    assert (again["created"], again["updated"]) == (0, 2)

    names = {c.name: c.status for c in db_session.query(Customer).all()}
    assert names == {"Acme SA": "active", "Beta GmbH": "prospect"}

    other = _director(client, company="Autre Société", email="x@autre.example")
    assert client.get("/customers", headers=other).json() == []
    plan = client.get("/configuration/integration-plan", headers=headers).json()
    assert plan["imports"][0]["created"] == 2


def test_excel_product_import_reads_prices_and_links_suppliers(client, db_session):
    headers = _director(client)
    client.post("/configuration/imports/suppliers", headers=headers, files={"file": ("f.csv", b"Fournisseur,Pays\nTexas Chips,USA\n")})
    book = Workbook()
    sheet = book.active
    sheet.append(["Référence", "Désignation", "Prix d'achat", "Prix de vente", "Fournisseur"])
    sheet.append(["STM32F4", "Microcontrôleur", "4,10", "5.90", "Texas Chips"])
    sheet.append(["LM317", "Régulateur", 0.35, 0.9, ""])
    buffer = io.BytesIO()
    book.save(buffer)
    res = client.post("/configuration/imports/products", headers=headers, files={"file": ("articles.xlsx", buffer.getvalue())})
    assert res.status_code == 200, res.text
    assert res.json()["created"] == 2
    products = {p.sku: p for p in db_session.query(Product).all()}
    assert products["STM32F4"].unit_cost == 4.10 and products["STM32F4"].sale_price == 5.9
    assert products["STM32F4"].supplier_id is not None and products["LM317"].supplier_id is None


def test_fec_import_creates_third_parties_and_a_summary(client):
    headers = _director(client)
    fec = (
        "JournalCode\tEcritureDate\tCompteNum\tCompAuxNum\tCompAuxLib\tDebit\tCredit\n"
        "VE\t20250105\t411000\tC1\tAcme SA\t1200,00\t0,00\n"
        "VE\t20250105\t707000\t\t\t0,00\t1000,00\n"
        "AC\t20250110\t401000\tF1\tTexas Chips\t0,00\t600,00\n"
        "AC\t20250110\t607000\t\t\t500,00\t0,00\n"
    ).encode()
    res = client.post("/configuration/imports/fec", headers=headers, files={"file": ("fec.txt", fec)}, params={"tool": "pennylane"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 2 and body["summary"]["revenue"] == 1000.0 and body["summary"]["purchases"] == 500.0
    assert [c["name"] for c in client.get("/customers", headers=headers).json()] == ["Acme SA"]
    assert [s["name"] for s in client.get("/suppliers", headers=headers).json()] == ["Texas Chips"]


@pytest.mark.parametrize("name,content", [("vide.csv", b""), ("sansnom.csv", b"Pays,Statut\nFrance,actif\n"), ("vieux.xls", b"abc")])
def test_bad_files_are_refused_with_a_clear_message(client, name, content):
    headers = _director(client)
    res = client.post("/configuration/imports/customers", headers=headers, files={"file": (name, content)})
    assert res.status_code == 422 and res.json()["detail"]
    res = client.post("/configuration/imports/fec", headers=headers, files={"file": ("fec.txt", b"a,b\n1,2\n")})
    assert res.status_code == 422


def test_no_demonstration_data_is_offered_to_a_real_company(client):
    headers = _director(client)
    assert client.get("/connectors", headers=headers).json() == {"connectors": []}
    res = client.post("/connectors/email/sync", headers=headers)
    assert res.status_code == 409 and "autorisation" in res.json()["detail"]
    mailboxes = client.get("/communications/mailboxes", headers=headers).json()
    assert mailboxes["providers"] == []


def test_website_audit_never_falls_back_to_the_demo_site(client):
    headers = _director(client)
    res = client.post("/website/audit", headers=headers)
    assert res.status_code in (200, 201), res.text
    body = res.json()
    assert body.get("mode") != "real" and body.get("status") == "failed"
    assert "démonstration" in str(body)
