"""The Analyste's full analysis, as text another agent can read.

Built from the company's own data, ordered by what the request is about:
the items that match the request come first, then risks and opportunities,
then sales, purchases, products and stock. Cut to a budget, never invented.
"""

import re
import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.entities import Customer, Opportunity, Product, Risk, StockPosition, Supplier, Transaction
from app.core.entities.transaction import TransactionStatus, TransactionType

BUDGET = 16000


def _terms(focus: str | None) -> list[str]:
    words = re.findall(r"[\w\-\.]{4,}", (focus or "").lower())
    stop = {"avec", "pour", "dans", "cette", "leur", "leurs", "sont", "faire", "chercher", "cherche", "analyse", "veilleur", "prix", "site", "sites"}
    return [w for w in dict.fromkeys(words) if w not in stop][:12]


def _eur(value: float | None) -> str:
    return "?" if value is None else f"{value:,.0f} €".replace(",", " ")


def build(session: Session, company_id: uuid.UUID, focus: str | None = None, budget: int = BUDGET) -> str:
    live = (Transaction.status != TransactionStatus.CANCELLED)
    sections: list[tuple[str, list[str]]] = []

    products = session.query(func.count(Product.id)).filter_by(company_id=company_id).scalar() or 0
    suppliers = session.query(func.count(Supplier.id)).filter_by(company_id=company_id).scalar() or 0
    customers = session.query(func.count(Customer.id)).filter_by(company_id=company_id).scalar() or 0
    sales_total = session.query(func.sum(Transaction.amount)).filter(Transaction.company_id == company_id, Transaction.type.in_((TransactionType.SALES_ORDER, TransactionType.INVOICE)), live).scalar()
    buy_total = session.query(func.sum(Transaction.amount)).filter(Transaction.company_id == company_id, Transaction.type == TransactionType.PURCHASE_ORDER, live).scalar()
    sections.append(("Vue d'ensemble", [f"{products} produits, {suppliers} fournisseurs, {customers} clients/prospects. Ventes cumulées : {_eur(sales_total)}. Achats cumulés : {_eur(buy_total)}."]))

    terms = _terms(focus)
    if terms:
        lines: list[str] = []
        for term in terms:
            like = f"%{term}%"
            for p in session.query(Product).filter(Product.company_id == company_id, or_(Product.name.ilike(like), Product.sku.ilike(like), Product.brand.ilike(like), Product.category.ilike(like))).limit(8).all():
                stock = session.query(func.sum(StockPosition.quantity)).filter_by(product_id=p.id).scalar()
                lines.append(f"Produit {p.name} (réf. {p.sku or '—'}, marque {p.brand or '?'}) : coût {p.unit_cost if p.unit_cost is not None else '?'}, prix de vente {p.sale_price if p.sale_price is not None else '?'}, stock {int(stock) if stock else 0}")
            for s in session.query(Supplier).filter(Supplier.company_id == company_id, Supplier.name.ilike(like)).limit(5).all():
                lines.append(f"Fournisseur {s.name} ({s.country or '?'}), conditions de paiement : {s.payment_terms or '?'}")
            for c in session.query(Customer).filter(Customer.company_id == company_id, Customer.name.ilike(like)).limit(5).all():
                lines.append(f"Client {c.name} ({c.country or '?'}, {c.status})")
        sections.append(("Éléments de vos données liés à la demande", list(dict.fromkeys(lines))[:40]))

    risks = session.query(Risk).filter(Risk.company_id == company_id).order_by(Risk.created_at.desc()).limit(40).all()
    sections.append(("Risques détectés", [f"[{getattr(r.severity, 'value', r.severity)}] {r.title}" + (f" : {r.description}" if r.description else "") for r in risks] or ["Aucun."]))
    opps = session.query(Opportunity).filter(Opportunity.company_id == company_id).order_by(Opportunity.created_at.desc()).limit(40).all()
    sections.append(("Opportunités détectées", [f"{o.title}" + (f" : {o.description}" if o.description else "") for o in opps] or ["Aucune."]))

    month = (func.strftime("%Y-%m", Transaction.occurred_at) if session.bind.dialect.name == "sqlite" else func.to_char(Transaction.occurred_at, "YYYY-MM")).label("month")
    by_month = (
        session.query(month, func.sum(Transaction.amount))
        .filter(Transaction.company_id == company_id, Transaction.type.in_((TransactionType.SALES_ORDER, TransactionType.INVOICE)), live)
        .group_by(month).all()
    )
    by_month = sorted(by_month)[-12:]
    sections.append(("Ventes par mois (12 derniers)", [", ".join(f"{m} : {_eur(v)}" for m, v in by_month)] if by_month else ["Aucune vente enregistrée."]))

    top_customers = (
        session.query(Customer.name, Customer.country, func.sum(Transaction.amount)).join(Transaction, Transaction.customer_id == Customer.id)
        .filter(Customer.company_id == company_id, Transaction.type.in_((TransactionType.SALES_ORDER, TransactionType.INVOICE)), live).group_by(Customer.id).order_by(func.sum(Transaction.amount).desc()).limit(12).all()
    )
    sections.append(("Meilleurs clients (chiffre d'affaires)", [f"{n} ({c or '?'}) : {_eur(v)}" for n, c, v in top_customers] or ["Aucun."]))
    top_suppliers = (
        session.query(Supplier.name, Supplier.country, Supplier.payment_terms, func.sum(Transaction.amount)).join(Transaction, Transaction.supplier_id == Supplier.id)
        .filter(Supplier.company_id == company_id, Transaction.type == TransactionType.PURCHASE_ORDER, live).group_by(Supplier.id).order_by(func.sum(Transaction.amount).desc()).limit(12).all()
    )
    sections.append(("Principaux fournisseurs (achats)", [f"{n} ({c or '?'}, paiement {t or '?'}) : {_eur(v)}" for n, c, t, v in top_suppliers] or ["Aucun."]))
    top_products = (
        session.query(Product.name, Product.sku, Product.unit_cost, Product.sale_price, func.sum(Transaction.amount)).join(Transaction, Transaction.product_id == Product.id)
        .filter(Product.company_id == company_id, Transaction.type.in_((TransactionType.SALES_ORDER, TransactionType.INVOICE)), live).group_by(Product.id).order_by(func.sum(Transaction.amount).desc()).limit(15).all()
    )
    def margin(cost, price):
        return f", marge {round((price - cost) / price * 100)} %" if cost is not None and price else ""
    sections.append(("Produits les plus vendus", [f"{n} ({s or '—'}) : ventes {_eur(v)}, coût {c if c is not None else '?'}, prix {p if p is not None else '?'}{margin(c, p)}" for n, s, c, p, v in top_products] or ["Aucun."]))
    stock = (
        session.query(Product.name, Product.sku, Product.brand, func.sum(StockPosition.quantity)).join(StockPosition, StockPosition.product_id == Product.id)
        .filter(Product.company_id == company_id).group_by(Product.id).order_by(func.sum(StockPosition.quantity).desc()).limit(15).all()
    )
    sections.append(("Plus gros stocks", [f"{n} ({s or '—'}, {b or '?'}) : {int(q or 0)}" for n, s, b, q in stock] or ["Aucun."]))
    brands = session.query(Product.brand, func.count(Product.id)).filter(Product.company_id == company_id, Product.brand.isnot(None)).group_by(Product.brand).order_by(func.count(Product.id).desc()).limit(12).all()
    sections.append(("Marques présentes", [", ".join(f"{b} ({c})" for b, c in brands)] if brands else ["Aucune."]))

    out: list[str] = []
    used = 0
    for title, lines in sections:
        block = f"## {title}\n" + "\n".join(f"- {l}" for l in lines)
        if used + len(block) > budget:
            block = block[: max(0, budget - used)].rsplit("\n", 1)[0]
            if not block:
                break
        out.append(block)
        used += len(block)
    return "\n\n".join(out)
