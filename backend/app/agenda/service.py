"""The company calendar.

Two sources, merged at read time:
- events somebody wrote by hand (table calendar_events);
- events the AI places from the company's own data and sorts by kind:
  sales and purchases booked (one line per day and kind), payments and
  deliveries expected, documents due or to follow up, risks and
  opportunities detected, actions due.

Nothing is invented: every AI event comes from a real record and carries
the object it comes from, so the person can open the source. What a
profile may see is limited to what its permissions already allow.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.access import policy as access
from app.core.entities import (
    CalendarEvent,
    CommercialDocument,
    Customer,
    Opportunity,
    PaymentInstallment,
    Risk,
    Supplier,
    Task,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.core.entities.commercial_document import DocumentKind

MAX_RANGE_DAYS = 100

# kind -> (label fr, group). The groups are the filters shown above the calendar.
KINDS: dict[str, tuple[str, str]] = {
    "sale": ("Ventes", "money"),
    "purchase": ("Achats", "money"),
    "payment": ("Paiement attendu", "money"),
    "delivery": ("Livraison attendue", "operations"),
    "follow_up": ("À relancer", "operations"),
    "deadline": ("Échéance", "operations"),
    "risk": ("Risque détecté", "ai"),
    "opportunity": ("Opportunité détectée", "ai"),
    "action": ("Action", "ai"),
    "meeting": ("Rendez-vous", "mine"),
    "trade_show": ("Salon / événement", "mine"),
    "other": ("Autre", "mine"),
}
MANUAL_KINDS = ("meeting", "trade_show", "deadline", "other")


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _item(kind: str, title: str, at: datetime, *, source: str = "ai", now: datetime, amount: float | None = None,
          detail: str | None = None, entity_type: str | None = None, entity_id: uuid.UUID | None = None,
          event_id: uuid.UUID | None = None, ends_at: datetime | None = None, all_day: bool = True, count: int = 1) -> dict:
    at = aware(at)
    return {
        "id": str(event_id) if event_id else f"{kind}:{entity_id or title}:{at.date().isoformat()}",
        "kind": kind,
        "kind_label": KINDS[kind][0],
        "group": KINDS[kind][1],
        "title": title,
        "at": at.isoformat(),
        "ends_at": aware(ends_at).isoformat() if ends_at else None,
        "all_day": all_day,
        "period": "past" if at < now else "upcoming",
        "source": source,
        "amount": round(amount, 2) if amount is not None else None,
        "detail": detail,
        "count": count,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
    }


def build_calendar(db: Session, user, start: datetime, end: datetime) -> dict:
    now = datetime.now(timezone.utc)
    start, end = aware(start), aware(end)
    items: list[dict] = []

    def inside(d: datetime | None) -> bool:
        d = aware(d)
        return d is not None and start <= d < end

    can = user.can
    names_c = {c.id: c.name for c in db.query(Customer).all()} if (can(access.VIEW_SALES) or can(access.VIEW_FINANCE)) else {}
    names_s = {s.id: s.name for s in db.query(Supplier).all()} if (can(access.VIEW_PROCUREMENT) or can(access.VIEW_FINANCE)) else {}

    # --- booked sales and purchases, one line per day and kind
    if can(access.VIEW_FINANCE) or can(access.VIEW_SALES) or can(access.VIEW_PROCUREMENT):
        rows = (
            db.query(Transaction)
            .filter(Transaction.occurred_at >= start, Transaction.occurred_at < end, Transaction.status != TransactionStatus.CANCELLED)
            .all()
        )
        groups: dict[tuple, list[Transaction]] = defaultdict(list)
        for t in rows:
            is_sale = t.type == TransactionType.SALES_ORDER
            if is_sale and not (can(access.VIEW_SALES) or can(access.VIEW_FINANCE)):
                continue
            if not is_sale and not (can(access.VIEW_PROCUREMENT) or can(access.VIEW_FINANCE)):
                continue
            groups[("sale" if is_sale else "purchase", aware(t.occurred_at).date())].append(t)
        for (kind, day), txs in groups.items():
            total = sum(t.amount for t in txs)
            parties = sorted({(names_c if kind == "sale" else names_s).get(t.customer_id if kind == "sale" else t.supplier_id, "") for t in txs} - {""})
            label = KINDS[kind][0]
            title = f"{label} : {len(txs)} · {total:,.0f} €".replace(",", " ")
            first = txs[0]
            items.append(_item(
                kind, title, datetime(day.year, day.month, day.day, tzinfo=timezone.utc), now=now, amount=total, count=len(txs),
                detail=", ".join(parties[:4]) + ("…" if len(parties) > 4 else "") or None,
                entity_type="transaction" if len(txs) == 1 else None, entity_id=first.id if len(txs) == 1 else None,
            ))

        # --- deliveries promised by suppliers (still open)
        if can(access.VIEW_PROCUREMENT):
            for t in db.query(Transaction).filter(Transaction.expected_at >= start, Transaction.expected_at < end, Transaction.type == TransactionType.PURCHASE_ORDER, Transaction.status != TransactionStatus.CANCELLED).all():
                items.append(_item("delivery", f"Livraison attendue : {names_s.get(t.supplier_id, 'fournisseur')}", t.expected_at, now=now,
                                   amount=t.amount, entity_type="transaction", entity_id=t.id))

    # --- documents due / to follow up, and installments
    if can(access.VIEW_SALES) or can(access.VIEW_PROCUREMENT) or can(access.VIEW_FINANCE):
        sales_kinds = {DocumentKind.CUSTOMER_REQUEST, DocumentKind.CUSTOMER_QUOTE, DocumentKind.CUSTOMER_ORDER, DocumentKind.CUSTOMER_DELIVERY, DocumentKind.CUSTOMER_INVOICE}
        for d in db.query(CommercialDocument).filter(CommercialDocument.completed_at.is_(None)).all():
            is_sale = d.kind in sales_kinds
            if is_sale and not (can(access.VIEW_SALES) or can(access.VIEW_FINANCE)):
                continue
            if not is_sale and not (can(access.VIEW_PROCUREMENT) or can(access.VIEW_FINANCE)):
                continue
            who = (names_c.get(d.customer_id) if is_sale else names_s.get(d.supplier_id)) or ""
            label = d.title or d.number
            if inside(d.due_at):
                invoice = d.kind in (DocumentKind.CUSTOMER_INVOICE, DocumentKind.SUPPLIER_INVOICE)
                items.append(_item("payment" if invoice else "deadline", f"{'Échéance facture' if invoice else 'Échéance'} {d.number}", d.due_at, now=now, detail=f"{who} · {label}".strip(" ·"),
                                   entity_type="commercial_document", entity_id=d.id))
            if inside(d.follow_up_at):
                items.append(_item("follow_up", f"À relancer : {who or d.number}", d.follow_up_at, now=now, detail=label, entity_type="commercial_document", entity_id=d.id))
        for p in db.query(PaymentInstallment).filter(PaymentInstallment.due_at >= start, PaymentInstallment.due_at < end).all():
            items.append(_item("payment", f"Échéance de paiement {p.label or ''}".strip(), p.due_at, now=now, amount=p.amount, entity_type="commercial_document", entity_id=p.document_id))

    # --- what the AI detected
    if can(access.VIEW_INTELLIGENCE):
        for r in db.query(Risk).filter(Risk.created_at >= start, Risk.created_at < end).all():
            items.append(_item("risk", r.title, r.created_at, now=now, detail=r.severity.value, entity_type="risk", entity_id=r.id))
        for o in db.query(Opportunity).filter(Opportunity.created_at >= start, Opportunity.created_at < end).all():
            items.append(_item("opportunity", o.title, o.created_at, now=now, entity_type="opportunity", entity_id=o.id))

    # --- actions with a due date
    if can(access.VIEW_ACTIONS):
        for t in db.query(Task).filter(Task.due_at >= start, Task.due_at < end).all():
            items.append(_item("action", t.title, t.due_at, now=now, detail=t.status.value, entity_type="task", entity_id=t.id))

    # --- written by hand
    for e in db.query(CalendarEvent).filter(CalendarEvent.starts_at >= start, CalendarEvent.starts_at < end).all():
        items.append(_item(e.kind if e.kind in KINDS else "other", e.title, e.starts_at, source="manual", now=now, detail=e.notes,
                           event_id=e.id, ends_at=e.ends_at, all_day=e.all_day))

    items.sort(key=lambda i: i["at"])
    return {"start": start.isoformat(), "end": end.isoformat(), "now": now.isoformat(), "kinds": {k: {"label": v[0], "group": v[1]} for k, v in KINDS.items()}, "events": items}
