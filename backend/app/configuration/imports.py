"""Real data import from the files every business tool can export.

CSV (comma, semicolon or tab; UTF-8 or Windows-1252), Excel (.xlsx) and the
French FEC (Fichier des Écritures Comptables). Columns are recognised by
meaning, not by exact name, so an export from Sage, Odoo or a hand-made Excel
sheet lands in the right fields. Nothing is invented: a row without a name is
skipped and reported, and re-importing the same file updates, never duplicates.
"""

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
import unicodedata
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.entities import Customer, Product, Supplier, Transaction
from app.core.entities.transaction import TransactionStatus, TransactionType

MAX_BYTES = 15 * 1024 * 1024
MAX_ROWS = 50_000


class ImportError_(ValueError):
    """The file cannot be read as the requested kind of data."""


@dataclass
class ImportResult:
    kind: str
    rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    problems: list[str] = field(default_factory=list)
    recognised_columns: dict[str, str] = field(default_factory=dict)


def _norm(text: object) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return "".join(ch for ch in text.lower() if ch.isalnum())


_SYNONYMS: dict[str, dict[str, tuple[str, ...]]] = {
    "customers": {
        "name": ("nom", "name", "client", "raisonsociale", "societe", "entreprise", "company", "compte", "accountname", "intitule", "libelle", "denomination", "customername"),
        "country": ("pays", "country", "paysclient"),
        "status": ("statut", "status", "etat", "type"),
        "notes": ("notes", "note", "commentaire", "commentaires", "remarque", "observations"),
    },
    "suppliers": {
        "name": ("nom", "name", "fournisseur", "raisonsociale", "societe", "entreprise", "company", "supplier", "intitule", "libelle", "denomination", "suppliername"),
        "country": ("pays", "country"),
        "payment_terms": ("conditionsdepaiement", "paymentterms", "echeance", "delaidepaiement", "reglement", "conditionsreglement"),
    },
    "products": {
        "name": ("nom", "name", "designation", "article", "produit", "libelle", "titre", "product", "description"),
        "sku": ("sku", "reference", "ref", "codearticle", "code", "partnumber", "pn", "mpn", "refarticle"),
        "unit_cost": ("prixachat", "coutunitaire", "unitcost", "cost", "cout", "prixdachat", "pa", "purchaseprice", "cump", "coutderevient"),
        "sale_price": ("prixvente", "prixdevente", "pv", "price", "prix", "saleprice", "tarif", "prixht", "pvht"),
        "category": ("categorie", "category", "famille", "gamme", "type"),
        "brand": ("marque", "brand", "fabricant", "manufacturer", "constructeur"),
        "unit": ("unite", "unit", "uom"),
        "supplier": ("fournisseur", "supplier", "vendor"),
    },
}

REQUIRED = {"customers": "name", "suppliers": "name", "products": "name"}


def read_table(filename: str, content: bytes) -> list[dict[str, str]]:
    if len(content) > MAX_BYTES:
        raise ImportError_("Fichier trop volumineux (15 Mo maximum).")
    if not content:
        raise ImportError_("Le fichier est vide.")
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm") or content[:2] == b"PK":
        return _read_xlsx(content)
    if name.endswith(".xls") or content[:4] == b"\xd0\xcf\x11\xe0":
        return _read_xls(content)
    return _read_csv(content)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _read_csv(content: bytes) -> list[dict[str, str]]:
    text = _decode(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    return _rows_to_dicts(rows)


def _read_xlsx(content: bytes) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any parser failure is "unreadable file"
        raise ImportError_("Le fichier Excel n'a pas pu être lu.") from exc
    sheet = workbook.worksheets[0]
    rows = [["" if v is None else str(v) for v in row] for row in sheet.iter_rows(values_only=True)]
    return _rows_to_dicts(rows)


def _read_xls(content: bytes) -> list[dict[str, str]]:
    """Old Excel format (.xls, 97-2003). First sheet only."""

    import xlrd

    try:
        sheet = xlrd.open_workbook(file_contents=content).sheet_by_index(0)
    except Exception as exc:  # noqa: BLE001 - any parser failure is "unreadable file"
        raise ImportError_("Le fichier Excel (.xls) n'a pas pu être lu.") from exc

    def cell(value: object) -> str:
        if isinstance(value, float):
            return str(int(value)) if value == int(value) else repr(value)
        return str(value)

    return _rows_to_dicts([[cell(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)])


def _rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("Le fichier ne contient pas de ligne de données sous la ligne d'en-têtes.")
    header = [str(h).strip() for h in rows[0]]
    if len(rows) - 1 > MAX_ROWS:
        raise ImportError_(f"Trop de lignes ({len(rows) - 1}, maximum {MAX_ROWS}).")
    keep = [i for i, h in enumerate(header) if h and h not in header[:i]]  # a repeated header keeps its first column
    return [{header[i]: (str(r[i]).strip() if i < len(r) else "") for i in keep} for r in rows[1:]]


def _map_columns(kind: str, columns: list[str]) -> dict[str, str]:
    wanted = _SYNONYMS[kind]
    mapping: dict[str, str] = {}
    for field_name, synonyms in wanted.items():
        for column in columns:
            if _norm(column) in synonyms and column not in mapping.values():
                mapping[field_name] = column
                break
    return mapping


def _number(text: str) -> float | None:
    cleaned = text.replace(" ", "").replace(" ", "").replace("€", "").replace("$", "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".") if cleaned.rfind(",") > cleaned.rfind(".") else cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


_CUSTOMER_STATUS = {"prospect": "prospect", "inactif": "inactive", "inactive": "inactive", "actif": "active", "active": "active"}


def import_entities(session: Session, company_id: uuid.UUID, kind: str, rows: list[dict[str, str]]) -> ImportResult:
    result = ImportResult(kind=kind, rows=len(rows))
    columns = list(rows[0].keys()) if rows else []
    mapping = _map_columns(kind, columns)
    result.recognised_columns = mapping
    required = REQUIRED[kind]
    if required not in mapping:
        raise ImportError_(
            "Colonne du nom introuvable. Colonnes lues : " + ", ".join(columns[:12]) + ". Ajoutez une colonne « Nom » (ou « Client », « Fournisseur », « Désignation »)."
        )

    model = {"customers": Customer, "suppliers": Supplier, "products": Product}[kind]
    existing: dict[str, object] = {}
    for row in session.query(model).filter_by(company_id=company_id).all():
        key = _norm(row.sku) if kind == "products" and row.sku else _norm(row.name)
        existing[key] = row
    suppliers = {_norm(s.name): s for s in session.query(Supplier).filter_by(company_id=company_id).all()} if kind == "products" else {}

    for line_number, row in enumerate(rows, start=2):
        values = {f: row.get(col, "").strip() for f, col in mapping.items()}
        name = values.get("name", "")
        if not name:
            result.skipped += 1
            if len(result.problems) < 10:
                result.problems.append(f"Ligne {line_number} ignorée : nom vide.")
            continue
        key = _norm(values.get("sku")) if kind == "products" and values.get("sku") else _norm(name)
        target = existing.get(key)
        created = target is None
        if created:
            target = model(company_id=company_id, name=name[:255])
            session.add(target)
            existing[key] = target
        else:
            target.name = name[:255]
        if kind in ("customers", "suppliers") and values.get("country"):
            target.country = values["country"][:120]
        if kind == "customers":
            if values.get("status"):
                target.status = _CUSTOMER_STATUS.get(_norm(values["status"]), target.status or "active")
            if values.get("notes"):
                target.notes = values["notes"]
        if kind == "suppliers" and values.get("payment_terms"):
            target.payment_terms = values["payment_terms"][:120]
        if kind == "products":
            for text_field, limit in (("sku", 120), ("category", 120), ("brand", 120), ("unit", 30)):
                if values.get(text_field):
                    setattr(target, text_field, values[text_field][:limit])
            for number_field in ("unit_cost", "sale_price"):
                if values.get(number_field):
                    number = _number(values[number_field])
                    if number is not None:
                        setattr(target, number_field, number)
            supplier = suppliers.get(_norm(values.get("supplier")))
            if supplier is not None:
                target.supplier_id = supplier.id
        if created:
            result.created += 1
        else:
            result.updated += 1
    session.flush()
    return result


# --- Stock list (physical stock of the company) --------------------------------

_STOCK_COLUMNS = {
    "model": ("model", "modele", "reference", "ref", "sku", "partnumber", "pn", "mpn", "designation", "article"),
    "quantity": ("quantity", "quantite", "qty", "qte", "stock", "stockphysique"),
    "location": ("emplacement", "location", "localisation", "rayon", "depot", "entrepot"),
    "manufacturer": ("manufacturer", "fabricant", "constructeur", "marque", "brand"),
    "category": ("categories", "category", "categorie", "famille", "gamme"),
    "date_code": ("dc", "datecode"),
}
_EMPTY_MARKS = {"", "-", "--", "n/a", "na", "none", "null"}


def _clean(text: str) -> str:
    return "" if text.strip().lower() in _EMPTY_MARKS else text.strip()


def _stock_mapping(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for field_name, synonyms in _STOCK_COLUMNS.items():
        for column in columns:
            if _norm(column) in synonyms and column not in mapping.values():
                mapping[field_name] = column
                break
    return mapping


def looks_like_stock(columns: list[str]) -> bool:
    mapping = _stock_mapping(columns)
    return "model" in mapping and "quantity" in mapping and "location" in mapping


def import_stock(session: Session, company_id: uuid.UUID, rows: list[dict[str, str]], filename: str) -> ImportResult:
    """The company's own physical stock: one product per reference, one stock
    position per (product, location, date code). Quantities are DECLARED by the
    file; re-importing updates them, never duplicates."""

    from app.core.entities.base import ValueBasis
    from app.core.entities.catalog import StockKind, StockPosition

    result = ImportResult(kind="stock", rows=len(rows))
    mapping = _stock_mapping(list(rows[0].keys()) if rows else [])
    result.recognised_columns = mapping
    if "model" not in mapping or "quantity" not in mapping:
        raise ImportError_("Colonnes « Référence » (ou Model) et « Quantité » introuvables.")

    products = {_norm(p.sku or p.name): p for p in session.query(Product).filter_by(company_id=company_id).all()}
    positions = {(pos.product_id, pos.location): pos for pos in session.query(StockPosition).filter_by(company_id=company_id, kind=StockKind.PHYSICAL).all() if pos.supplier_id is None}
    totals: dict[tuple[str, str], float] = {}
    meta: dict[str, dict[str, str]] = {}
    for line_number, row in enumerate(rows, start=2):
        values = {f: row.get(col, "") for f, col in mapping.items()}
        model = values.get("model", "").strip()
        quantity = _number(values.get("quantity", ""))
        if not model or quantity is None or quantity < 0:
            result.skipped += 1
            if len(result.problems) < 10:
                result.problems.append(f"Ligne {line_number} ignorée : référence ou quantité illisible.")
            continue
        place = _clean(values.get("location", ""))
        code = _clean(values.get("date_code", ""))
        location = (place + (f" · DC {code}" if code else "")).strip()[:120]
        key = (_norm(model), location)
        totals[key] = totals.get(key, 0.0) + quantity
        meta.setdefault(_norm(model), {"model": model, "manufacturer": _clean(values.get("manufacturer", "")), "category": _clean(values.get("category", ""))})

    now = datetime.now(timezone.utc)
    for norm_model, info in meta.items():
        product = products.get(norm_model)
        if product is None:
            product = Product(company_id=company_id, name=info["model"][:255], sku=info["model"][:120])
            session.add(product)
            products[norm_model] = product
        if info["manufacturer"]:
            product.manufacturer = info["manufacturer"][:120]
        if info["category"] and not product.category:
            product.category = info["category"][:120]
    session.flush()
    for (norm_model, location), quantity in totals.items():
        product = products[norm_model]
        existing = positions.get((product.id, location))
        if existing is None:
            session.add(StockPosition(company_id=company_id, product_id=product.id, kind=StockKind.PHYSICAL, location=location, quantity=quantity,
                                      quantity_basis=ValueBasis.DECLARED, as_of=now, source=f"csv:{filename}"[:80]))
            result.created += 1
        else:
            existing.quantity, existing.as_of, existing.source = quantity, now, f"csv:{filename}"[:80]
            result.updated += 1
    session.flush()
    return result


# --- Prospect list (e.g. Corporama export) ----------------------------------------

_PROSPECT = {
    "name": "nomraisonsociale",
    "brand": "nomenseigne",
    "siren": "siren",
    "buyer": "contactachats",
    "buyer_mail": "mailachats",
    "generic_mail": "mailgenerique",
    "phone": "telephone",
    "naf": "nafliblledglobal",
    "city": "adressevilleville",
    "site": "siteweb",
    "comment": "commentaire",
}


def _find(columns: list[str], *needles: str) -> str | None:
    for column in columns:
        n = _norm(column)
        if all(t in n for t in needles):
            return column
    return None


def _exact(columns: list[str], normalised: str) -> str | None:
    return next((c for c in columns if _norm(c) == normalised), None)


def looks_like_prospects(columns: list[str]) -> bool:
    return _find(columns, "siren") is not None and _find(columns, "raisonsociale") is not None


def import_prospects(session: Session, company_id: uuid.UUID, rows: list[dict[str, str]]) -> ImportResult:
    """A purchased or exported list of companies to approach. They become
    customers with the status « prospect » (never counted as business done),
    with their purchasing contact and main executive as contacts."""

    from app.core.entities import Contact
    from app.core.entities.base import RelatedEntityType

    result = ImportResult(kind="prospects", rows=len(rows))
    columns = list(rows[0].keys()) if rows else []
    c_name = _find(columns, "raisonsociale")
    if c_name is None:
        raise ImportError_("Colonne « Nom : raison sociale » introuvable.")
    c = {
        "siren": _find(columns, "siren"),
        "brand": _find(columns, "enseigne"),
        "comment": _find(columns, "commentaire"),
        "buyer": _find(columns, "contactachats"),
        "buyer_mail": _find(columns, "mailachats"),
        "mail": _find(columns, "mailgenerique"),
        "phone": _find(columns, "telephone"),
        "naf": _exact(columns, _norm("NAF : libellé (global)")),
        "size": _find(columns, "effectifs", "libelle", "global"),
        "revenue": _find(columns, "ca", "derniere", "k"),
        "revenue_year": _find(columns, "derniere", "annee", "publication"),
        "street": _find(columns, "adresse", "rue"),
        "zip": _find(columns, "adresse", "codepostal"),
        "city": _find(columns, "adresse", "ville"),
        "site": _find(columns, "siteweb"),
        "d_first": _exact(columns, "dirigeant1prenom"),
        "d_last": _exact(columns, "dirigeant1nom"),
        "d_role": _exact(columns, "dirigeant1fonction"),
    }

    def get(row: dict[str, str], key: str) -> str:
        column = c.get(key)
        return row.get(column, "").strip() if column else ""

    existing = {_norm(x.name): x for x in session.query(Customer).filter_by(company_id=company_id).all()}
    known_contacts = {(x.related_entity_id, _norm(x.name)) for x in session.query(Contact).filter_by(company_id=company_id, related_entity_type=RelatedEntityType.CUSTOMER).all()}
    for line_number, row in enumerate(rows, start=2):
        name = row.get(c_name, "").strip()
        if not name:
            result.skipped += 1
            if len(result.problems) < 10:
                result.problems.append(f"Ligne {line_number} ignorée : nom vide.")
            continue
        key = _norm(name)
        target = existing.get(key)
        if target is not None and target.status != "prospect":
            result.skipped += 1  # already a real customer: a prospect list never downgrades it
            continue
        created = target is None
        if created:
            target = Customer(company_id=company_id, name=name[:255], country="France", status="prospect")
            session.add(target)
            existing[key] = target
        parts = [f"SIREN {get(row, 'siren')}" if get(row, "siren") else "", get(row, "brand") and f"Enseigne : {get(row, 'brand')}"]
        place = " ".join(x for x in (get(row, "zip"), get(row, "city")) if x)
        parts += [place, get(row, "naf"), get(row, "size") and f"Effectif : {get(row, 'size')}"]
        revenue = _number(get(row, "revenue"))
        if revenue is not None:
            parts.append(f"CA {revenue:,.0f} k€".replace(",", " ") + (f" ({get(row, 'revenue_year')})" if get(row, "revenue_year") else ""))
        parts += [get(row, "phone") and f"Tél. {get(row, 'phone')}", get(row, "mail"), get(row, "site"), get(row, "comment")]
        target.notes = " · ".join(str(p) for p in parts if p)[:2000]
        if created:
            result.created += 1
        else:
            result.updated += 1
        session.flush()
        people = []
        if get(row, "buyer"):
            people.append((get(row, "buyer").title(), get(row, "buyer_mail") or None, "Contact achats"))
        director = " ".join(x for x in (get(row, "d_first"), get(row, "d_last")) if x)
        if director:
            people.append((director.title(), None, get(row, "d_role") or "Dirigeant"))
        for person, mail, role in people:
            if (target.id, _norm(person)) in known_contacts:
                continue
            session.add(Contact(company_id=company_id, name=person[:255], email=(mail or "")[:255] or None, phone=get(row, "phone")[:50] or None, role=role[:120],
                                related_entity_type=RelatedEntityType.CUSTOMER, related_entity_id=target.id))
            known_contacts.add((target.id, _norm(person)))
    session.flush()
    return result


# --- FEC ------------------------------------------------------------------

_FEC_REQUIRED = ("compteNum", "ecritureDate", "debit", "credit")


def _fec_rows(content: bytes) -> list[dict[str, str]]:
    text = _decode(content)
    first = text.split("\n", 1)[0]
    delimiter = "\t" if first.count("\t") >= first.count("|") else "|"
    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as exc:  # binary content (an Excel file) is never a FEC
        raise ImportError_("Ce fichier n'est pas un FEC valide.") from exc
    table = _rows_to_dicts(rows)
    lowered = {k.lower(): k for k in table[0].keys()}
    for needed in _FEC_REQUIRED:
        if needed.lower() not in lowered:
            raise ImportError_("Ce fichier n'est pas un FEC valide : colonne « " + needed + " » absente.")
    return [{k.lower(): v for k, v in row.items()} for row in table]


def import_fec(session: Session, company_id: uuid.UUID, content: bytes) -> tuple[ImportResult, dict]:
    """Third parties (customers 411, suppliers 401) from the auxiliary
    accounts, and a financial summary computed from the entries."""

    rows = _fec_rows(content)
    result = ImportResult(kind="fec", rows=len(rows))
    customers: dict[str, str] = {}
    suppliers: dict[str, str] = {}
    revenue = purchases = 0.0
    dates: list[str] = []
    for row in rows:
        account = row.get("comptenum", "")
        label = row.get("compauxlib", "").strip()
        aux_num = row.get("compauxnum", "").strip()
        debit = _number(row.get("debit", "")) or 0.0
        credit = _number(row.get("credit", "")) or 0.0
        if account.startswith("411") and label:
            customers[_norm(label)] = label
        elif account.startswith("401") and label:
            suppliers[_norm(label)] = label
        elif aux_num and label and account.startswith("4"):
            pass
        if account.startswith("70"):
            revenue += credit - debit
        elif account.startswith("60"):
            purchases += debit - credit
        if row.get("ecrituredate"):
            dates.append(row["ecrituredate"])

    def upsert(model, names: dict[str, str]) -> None:
        known = {_norm(r.name): r for r in session.query(model).filter_by(company_id=company_id).all()}
        for key, label in names.items():
            if key in known:
                result.updated += 1
            else:
                session.add(model(company_id=company_id, name=label[:255]))
                result.created += 1

    upsert(Customer, customers)
    upsert(Supplier, suppliers)
    session.flush()
    posted = _post_fec_transactions(session, company_id, rows)
    result.created += posted[0]
    result.updated += posted[1]
    summary = {
        "customers_found": len(customers),
        "suppliers_found": len(suppliers),
        "revenue": round(revenue, 2),
        "purchases": round(purchases, 2),
        "entries": len(rows),
        "sales_posted": posted[2],
        "purchases_posted": posted[3],
        "from": min(dates) if dates else None,
        "to": max(dates) if dates else None,
    }
    return result, summary


def detect_kind(filename: str, content: bytes) -> str:
    """Which kind of data a file holds, from its content first, its name second."""

    name = _norm(filename)
    if any(token in name for token in ("fec", "ecriture", "grandlivre", "journal")):
        try:
            _fec_rows(content)
            return "fec"
        except ImportError_:
            pass
    try:
        _fec_rows(content)
        return "fec"
    except ImportError_:
        pass
    rows = read_table(filename, content)
    raw_columns = list(rows[0].keys())
    if looks_like_prospects(raw_columns):
        return "prospects"
    if looks_like_stock(raw_columns):
        return "stock"
    columns = [_norm(c) for c in rows[0].keys()]
    has_date = any(c in _TX_COLUMNS["date"] for c in columns)
    has_amount = any(c in _TX_COLUMNS["amount"] for c in columns) or (any(c in _TX_COLUMNS["quantity"] for c in columns) and any(c in _TX_COLUMNS["unit_price"] for c in columns))
    if has_date and has_amount:
        buy_hint = any(t in name for t in ("achat", "purchase", "fournisseur", "supplier", "depense"))
        sale_hint = any(t in name for t in ("vente", "sales", "facture", "invoice", "client", "customer", "commande"))
        has_supplier_col = any(c in ("fournisseur", "supplier", "vendor", "nomfournisseur") for c in columns)
        return "purchases" if (buy_hint and not sale_hint) or (has_supplier_col and not any(c in ("client", "customer", "nomclient") for c in columns)) else "sales"
    if any(c in _SYNONYMS["products"]["sku"] + _SYNONYMS["products"]["unit_cost"] + _SYNONYMS["products"]["sale_price"] for c in columns):
        return "products"
    for kind, tokens in (("suppliers", ("fournisseur", "supplier", "vendor")), ("products", ("article", "produit", "product", "stock", "catalogue")), ("customers", ("client", "customer", "prospect"))):
        if any(t in name for t in tokens):
            return kind
    if any(c in ("fournisseur", "supplier", "vendor", "suppliername", "conditionsdepaiement", "paymentterms") for c in columns):
        return "suppliers"
    return "customers"


# --- Transactions (sales and purchases) ------------------------------------

_TX_COLUMNS = {
    "date": ("date", "datefacture", "datedevente", "datedecommande", "dateecriture", "datedoperation", "datedachat", "day", "jour"),
    "amount": ("montant", "montantht", "total", "totalht", "amount", "chiffredaffaires", "ca", "montantttc", "totalttc", "valeur"),
    "quantity": ("quantite", "qte", "quantity", "qty", "qte"),
    "unit_price": ("prixunitaire", "pu", "unitprice", "puht", "prixunitaireht"),
    "sku": ("reference", "sku", "ref", "codearticle", "partnumber", "pn", "refarticle"),
    "product": ("article", "produit", "designation", "product", "libelle", "description"),
    "status": ("statut", "status", "etat", "paye", "reglement"),
}
_TX_PARTY = {
    "sales": ("client", "customer", "nomclient", "raisonsociale", "societe", "acheteur", "compte"),
    "purchases": ("fournisseur", "supplier", "vendor", "nomfournisseur", "raisonsociale", "societe"),
}
_PAID_WORDS = ("paye", "regle", "paid", "soldee", "solde", "encaisse")


def _parse_date(text: str) -> datetime | None:
    text = (text or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y%m%d", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19] if "%H" in pattern else text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _tx_mapping(kind: str, columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    candidates = {**_TX_COLUMNS, "party": _TX_PARTY[kind]}
    for field_name, synonyms in candidates.items():
        for column in columns:
            if _norm(column) in synonyms and column not in mapping.values():
                mapping[field_name] = column
                break
    return mapping


def _party(session: Session, company_id: uuid.UUID, model, cache: dict, name: str):
    key = _norm(name)
    found = cache.get(key)
    if found is None:
        found = model(company_id=company_id, name=name[:255])
        session.add(found)
        session.flush()
        cache[key] = found
    return found


def import_transactions(session: Session, company_id: uuid.UUID, kind: str, rows: list[dict[str, str]]) -> ImportResult:
    """Sales (revenue) or purchases (costs) from a file: one row, one
    transaction. Customers, suppliers and products are matched by name or
    reference and created when they do not exist yet."""

    result = ImportResult(kind=kind, rows=len(rows))
    mapping = _tx_mapping(kind, list(rows[0].keys()) if rows else [])
    result.recognised_columns = mapping
    if "date" not in mapping or ("amount" not in mapping and not ("quantity" in mapping and "unit_price" in mapping)):
        raise ImportError_(
            "Colonnes introuvables. Il faut au minimum une date et un montant (ou une quantité et un prix unitaire). Colonnes lues : " + ", ".join(list(rows[0].keys())[:12]) + "."
        )

    ttype = TransactionType.SALES_ORDER if kind == "sales" else TransactionType.INVOICE
    party_model = Customer if kind == "sales" else Supplier
    parties = {_norm(r.name): r for r in session.query(party_model).filter_by(company_id=company_id).all()}
    products = {}
    for r in session.query(Product).filter_by(company_id=company_id).all():
        products[_norm(r.sku)] = r
        products.setdefault(_norm(r.name), r)
    existing = {t.external_ref: t for t in session.query(Transaction).filter(Transaction.company_id == company_id, Transaction.external_ref.like(f"file:{kind}:%")).all()}
    seen: dict[str, int] = {}

    for line_number, row in enumerate(rows, start=2):
        v = {f: row.get(col, "").strip() for f, col in mapping.items()}
        when = _parse_date(v.get("date", ""))
        quantity = _number(v.get("quantity", "")) if v.get("quantity") else None
        amount = _number(v.get("amount", "")) if v.get("amount") else None
        if amount is None and quantity is not None and v.get("unit_price"):
            unit = _number(v["unit_price"])
            amount = round(quantity * unit, 2) if unit is not None else None
        if when is None or amount is None:
            result.skipped += 1
            if len(result.problems) < 10:
                result.problems.append(f"Ligne {line_number} ignorée : " + ("date illisible." if when is None else "montant illisible."))
            continue
        digest = hashlib.sha1("|".join([v.get("date", ""), v.get("party", ""), v.get("amount", ""), v.get("sku", ""), v.get("product", ""), v.get("quantity", "")]).encode()).hexdigest()[:20]
        seen[digest] = seen.get(digest, 0) + 1
        ref = f"file:{kind}:{digest}:{seen[digest]}"

        party = _party(session, company_id, party_model, parties, v["party"]) if v.get("party") else None
        product = None
        product_key = _norm(v.get("sku")) or _norm(v.get("product"))
        if product_key:
            product = products.get(product_key)
            if product is None:
                product = Product(company_id=company_id, name=(v.get("product") or v.get("sku"))[:255], sku=(v.get("sku") or None))
                session.add(product)
                session.flush()
                products[product_key] = product
        status = TransactionStatus.PAID if any(w in _norm(v.get("status")) for w in _PAID_WORDS) else TransactionStatus.CONFIRMED

        tx = existing.get(ref)
        created = tx is None
        if created:
            tx = Transaction(company_id=company_id, type=ttype, external_ref=ref, amount=amount, occurred_at=when)
            session.add(tx)
        tx.amount, tx.occurred_at, tx.status, tx.quantity = amount, when, status, quantity
        tx.customer_id = party.id if kind == "sales" and party else None
        tx.supplier_id = party.id if kind == "purchases" and party else None
        tx.product_id = product.id if product else None
        result.created += 1 if created else 0
        result.updated += 0 if created else 1
    session.flush()
    return result


def _post_fec_transactions(session: Session, company_id: uuid.UUID, rows: list[dict[str, str]]) -> tuple[int, int, int, int]:
    """Each accounting entry that touches a customer account (411) becomes a
    sale, each one that touches a supplier account (401) a purchase, valued at
    the revenue (70) or expense (60-62) lines of the same entry, else at the
    third-party line. Lettered entries are settled."""

    entries: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        entries.setdefault((row.get("journalcode", ""), row.get("ecriturenum", "") or row.get("ecriturelib", "")), []).append(row)

    customers = {_norm(c.name): c for c in session.query(Customer).filter_by(company_id=company_id).all()}
    suppliers = {_norm(c.name): c for c in session.query(Supplier).filter_by(company_id=company_id).all()}
    existing = {t.external_ref: t for t in session.query(Transaction).filter(Transaction.company_id == company_id, Transaction.external_ref.like("fec:%")).all()}
    created = updated = sales = purchases = 0

    for (journal, number), lines in entries.items():
        party_411 = next((l for l in lines if l.get("comptenum", "").startswith("411") and l.get("compauxlib", "").strip()), None)
        party_401 = next((l for l in lines if l.get("comptenum", "").startswith("401") and l.get("compauxlib", "").strip()), None)
        if party_411 is None and party_401 is None:
            continue
        is_sale = party_411 is not None
        anchor = party_411 if is_sale else party_401
        if is_sale:
            amount = sum((_number(l.get("credit", "")) or 0.0) - (_number(l.get("debit", "")) or 0.0) for l in lines if l.get("comptenum", "").startswith("70"))
            if amount == 0:
                amount = (_number(anchor.get("debit", "")) or 0.0) - (_number(anchor.get("credit", "")) or 0.0)
        else:
            amount = sum((_number(l.get("debit", "")) or 0.0) - (_number(l.get("credit", "")) or 0.0) for l in lines if l.get("comptenum", "")[:2] in ("60", "61", "62"))
            if amount == 0:
                amount = (_number(anchor.get("credit", "")) or 0.0) - (_number(anchor.get("debit", "")) or 0.0)
        when = _parse_date(anchor.get("ecrituredate", ""))
        if when is None or amount == 0:
            continue
        ref = f"fec:{journal}:{number}"[:120]
        party = (customers if is_sale else suppliers).get(_norm(anchor.get("compauxlib")))
        tx = existing.get(ref)
        is_new = tx is None
        if is_new:
            tx = Transaction(company_id=company_id, external_ref=ref, type=TransactionType.SALES_ORDER if is_sale else TransactionType.INVOICE, amount=amount, occurred_at=when)
            session.add(tx)
        tx.amount, tx.occurred_at = amount, when
        tx.status = TransactionStatus.PAID if any(l.get("ecriturelet", "").strip() for l in lines if l.get("comptenum", "").startswith(("411", "401"))) else TransactionStatus.CONFIRMED
        tx.customer_id = party.id if is_sale and party else None
        tx.supplier_id = party.id if not is_sale and party else None
        created += 1 if is_new else 0
        updated += 0 if is_new else 1
        sales += 1 if is_sale else 0
        purchases += 0 if is_sale else 1
    session.flush()
    return created, updated, sales, purchases
