"""Real data import from the files every business tool can export.

CSV (comma, semicolon or tab; UTF-8 or Windows-1252), Excel (.xlsx) and the
French FEC (Fichier des Écritures Comptables). Columns are recognised by
meaning, not by exact name, so an export from Sage, Odoo or a hand-made Excel
sheet lands in the right fields. Nothing is invented: a row without a name is
skipped and reported, and re-importing the same file updates, never duplicates.
"""

import csv
import io
import unicodedata
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.entities import Customer, Product, Supplier

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
    if name.endswith(".xls"):
        raise ImportError_("Le format .xls ancien n'est pas lisible : enregistrez le fichier en .xlsx ou .csv.")
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


def _rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("Le fichier ne contient pas de ligne de données sous la ligne d'en-têtes.")
    header = [str(h).strip() for h in rows[0]]
    if len(rows) - 1 > MAX_ROWS:
        raise ImportError_(f"Trop de lignes ({len(rows) - 1}, maximum {MAX_ROWS}).")
    return [{header[i]: (str(r[i]).strip() if i < len(r) else "") for i in range(len(header)) if header[i]} for r in rows[1:]]


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


# --- FEC ------------------------------------------------------------------

_FEC_REQUIRED = ("compteNum", "ecritureDate", "debit", "credit")


def _fec_rows(content: bytes) -> list[dict[str, str]]:
    text = _decode(content)
    first = text.split("\n", 1)[0]
    delimiter = "\t" if first.count("\t") >= first.count("|") else "|"
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
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
    summary = {
        "customers_found": len(customers),
        "suppliers_found": len(suppliers),
        "revenue": round(revenue, 2),
        "purchases": round(purchases, 2),
        "entries": len(rows),
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
    columns = [_norm(c) for c in rows[0].keys()]
    if any(c in _SYNONYMS["products"]["sku"] + _SYNONYMS["products"]["unit_cost"] + _SYNONYMS["products"]["sale_price"] for c in columns):
        return "products"
    for kind, tokens in (("suppliers", ("fournisseur", "supplier", "vendor")), ("products", ("article", "produit", "product", "stock", "catalogue")), ("customers", ("client", "customer", "prospect"))):
        if any(t in name for t in tokens):
            return kind
    if any(c in ("fournisseur", "supplier", "vendor", "suppliername", "conditionsdepaiement", "paymentterms") for c in columns):
        return "suppliers"
    return "customers"
