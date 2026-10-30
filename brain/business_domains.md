# Step 23B — Business Domain Foundation

## Starting point (Step 23 audit)

The Step 23 audit (read-only, no code changed) found that the Data Core
already held everything needed to answer real Finance/Procurement/Sales
questions — `Supplier`, `Customer`, `Product`, `Transaction`,
`get_entity_context`, `app.core.analytics`'s trend functions, and
`HomeService.get_ai_priorities` for AI-generated signals — but none of it
was reachable from a working frontend page. `/data/*` and `/business/*`
routes existed only as `"Not implemented yet."` placeholders, and
`app/domains/finance/`, `app/domains/sales/`, `app/domains/crm/`,
`app/domains/marketing/`, `app/domains/hr/`, `app/domains/supply_chain/`
were empty modules. The audit also found one real data-loss bug:
`WebsiteInquiry.source` (e.g. `"quote_form"` vs `"pricing_page"`) was read
by the Mock Website connector but never stored anywhere on the
`Communication` row `ingest_website` created from it.

## What Step 23B built

A mid-task steering note from the user made the operating principle
explicit: never build something new that an existing abstraction already
does. Every page and endpoint below is a *view* over the Data Core, not a
new source of truth.

**Backend — generic read APIs** (`app/data/`):
- `GET /suppliers`, `/suppliers/{id}`, `/customers`, `/customers/{id}`,
  `/products`, `/products/{id}`, `/transactions`, `/transactions/{id}`.
- `app/data/service.py` composes `get_entity_context` (relational
  structure), `compute_supplier_delivery_performance`,
  `compute_customer_value_trend`, `compute_margin_trend`,
  `compute_unanswered_message_age` (the one domain metric each entity type
  already had), and `HomeService.get_ai_priorities` (intelligence signals,
  indexed by entity). No number here is computed twice.

**Backend — domain overviews** (`app/domains/{finance,procurement,sales}/`):
- `GET /finance/overview`, `/procurement/overview`, `/sales/overview`.
- Each one calls `app/data/service.py`'s own list functions
  (`list_suppliers`, `list_customers`, `list_transactions`) rather than
  re-querying the ORM, and filters `HomeService.get_ai_priorities` by
  `domain` ("finance"/"procurement"/"sales" — values that already existed
  on every Observable since Step 12).
- The one genuinely new computation: `compute_company_financials`
  (`app/core/analytics.py`) — company-wide total revenue, total costs and
  overall margin. This is a different granularity than
  `compute_margin_trend` (per-product, baseline-vs-recent), not a
  duplicate of it, and it is shared between Finance (revenue/costs/margin)
  and Procurement (whose "total spend" is exactly its `total_costs`) so
  the two views can never silently disagree on what the company spent.
- Procurement's `/overview` was added to the *existing*
  `app/domains/procurement/router.py` (already serving
  `POST /supplier-cost-changes` since Step 12) instead of a second,
  parallel router. Finance's and Sales's router/service/schemas fill the
  `app/domains/{finance,sales}/` modules that had been empty placeholders
  since Step 12's own explicit scope decision — no new module boundary,
  only content inside a boundary the architecture already reserved.
- All three overview endpoints tolerate a company-less (fresh, unseeded)
  install by returning zeroed-out defaults, matching `GET /home`'s own
  behavior, rather than a 404 on a page that is a primary nav destination.

**Frontend**:
- `/data/suppliers(/[id])`, `/data/customers(/[id])`,
  `/data/products(/[id])`, `/data/transactions` (list only — no detail
  view was required, and the list already surfaces every requested field).
- `/business/finance`, `/business/procurement`, `/business/sales` —
  overview stats, an Intelligence section (shared `IntelligenceCard`
  component), and recent activity, each linking back into the
  corresponding `/data/*` detail pages rather than duplicating them.
- `Sidebar.tsx` restructured into HOME / BUSINESS (Finance, Procurement,
  Sales) / DATA (Suppliers, Customers, Products, Transactions) /
  INTELLIGENCE (Risks, Opportunities, Decision Intelligence) / ACTIONS
  (Tasks) / AI (Ask AI). CRM, Marketing, HR and Supply Chain are
  deliberately absent from the sidebar — they remain exactly as
  unimplemented as the Step 12 scope decision left them.

**Corollary fixes**:
- `Communication.channel_detail` (migration `4ba6953c0de3`) — an additive
  column preserving `WebsiteInquiry.source`, fixing the audit-identified
  data loss in `ingest_website`.
- A few realistic `TransactionType.INVOICE` rows were seeded to exercise
  payment status (`PAID`/`CONFIRMED`) end-to-end. They had to be placed
  supplier-side only: `compute_margin_trend`'s cost-side query
  (`type.in_([PURCHASE_ORDER, INVOICE])`) does not check whether
  `supplier_id` or `customer_id` is set on a transaction, so a
  customer-side invoice would have been silently double-counted as a cost.
  Placed on two routine products outside every existing detection chain
  (Steel Bracket Set, Control Board Rev C) to avoid perturbing the four
  demo scenarios already validated in earlier steps.

## What was explicitly not built

Per the brief's own constraints and the Step 12 scope decision this step
did not revisit: no new database per domain, no per-domain AI agents, no
new intelligence engine, no parallel scoring system, no CRM pipeline or
Deal entity, no Invoice entity or payment engine — `TransactionType.INVOICE`
plus `TransactionStatus` remain sufficient. CRM, Marketing, HR and Supply
Chain frontend pages remain `"Not implemented yet."` placeholders, exactly
as before this step. `/intelligence/decision-intelligence` is linked from
the new sidebar (per the target structure) but is itself still a
placeholder — Decision Intelligence's real content is already surfaced via
Home's `get_decisions` and, in domain terms, isn't a Step 23B target.

## Verification

- 265 backend tests passing (261 before this step's own 4 new tests in
  `tests/test_domain_overviews.py`), zero regressions.
- `npm run build` compiles cleanly.
- Fresh-DB E2E: `alembic upgrade head` → `python -m data.seed` → live
  `curl` against all three overview endpoints and all four `/data/*`
  domains, confirmed real cross-linked data (e.g. `/finance/overview`
  correctly surfaces the Steel Frame Assembly margin-deterioration risk
  with the two seeded invoices reflected in `total_costs`); frontend pages
  rendered against the same running backend confirmed the same entity
  names appear in the actual HTML response, not just the JSON.
