# Data Core: Audit and Reinforcement (Step 20)

This document covers the audit of the Data Core's entities and relationships
performed for this step, what it found, what was fixed, and what stays
deliberately as-is. The Data Core is the one source of truth every layer
built since step 5 (Procurement) reads from — this step verified that claim
holds, rather than adding new functionality.

## Entities and their relationships (as of this step)

```text
Company
 ├── Supplier (company_id FK)
 │     ├── Product (supplier_id FK, nullable)
 │     └── Transaction (supplier_id FK, nullable)
 ├── Customer (company_id FK)
 │     └── Transaction (customer_id FK, nullable)
 └── Product (company_id FK)
       └── Transaction (product_id FK, nullable)  <-- ORM relationship added this step

Transaction: company_id (required) + supplier_id / customer_id / product_id (all nullable, independent FKs)

Contact, Document, Communication, Task, Risk, Opportunity:
  company_id (required) + LinkableMixin (related_entity_type + related_entity_id,
  a generic polymorphic pointer to Supplier/Customer/Product -- no native
  cross-table FK, application-level integrity only, an accepted prototype
  compromise documented since step 1)

EventLogEntry: event_type + payload (JSON) + source + correlation_id +
  occurred_at -- no company_id, no structured entity link (see below)
```

Every entity has `id` (UUID, `IdMixin`) and `created_at`/`updated_at`
(`TimestampMixin`). `RelatedEntityType` (`company | supplier | customer |
product | transaction`) is the one polymorphic vocabulary `LinkableMixin`
entities share — `company` and `transaction` are declared but never actually
used as a `related_entity_type` value by any current rule or seed data; kept
as headroom, not dead code to remove, since removing an unused enum member
carries no benefit and a small risk of missing a future use.

## What the audit found

1. **Supplier → Product, Supplier → Transaction, Customer → Transaction**:
   already correct — both the FK column and the SQLAlchemy `relationship()`
   (with `back_populates`) existed and were already exercised (e.g.
   `read_supplier`'s `product_count = len(supplier.products)`).
2. **Product → Transaction**: the FK column (`Transaction.product_id`)
   existed and was already used everywhere by direct filtered queries
   (`compute_margin_trend`, `read_transactions`, `get_entity_context`, ...),
   but **no ORM `relationship()` existed on `Product`** — an asymmetry
   against Supplier/Customer's own convenience relationship. Fixed: `Product.transactions`
   added, `Transaction.product`'s relationship given a matching
   `back_populates`. This is a pure mapping-level addition — no new column,
   no migration, no behavior change for any existing caller (every one of
   them already queried `Transaction` directly rather than traversing the
   relationship).
3. **Document / Communication → related entity**: already correct via
   `LinkableMixin`, exercised in `data/seed.py` (a Document linked to a
   Supplier, a Communication linked to a Customer).
4. **Event Log → related entity**: `EventLogEntry` has no structured entity
   link at all — every event type names its subject with whatever payload
   field makes sense for it (`entity_id` for Observation/Interpretation/
   Decision events, `supplier_id`/`product_id` for the reactive Procurement
   event, `related_entity_id` for Task/Action events, ...). This is a real
   inconsistency, but not a gap that blocks anything: every consumer that
   needs "events about entity X" already has a working query for its own
   event type(s) (`_recurrence_count`, `_already_interpreted`,
   `_already_decided`, ...). See "What was deliberately not changed" below
   for why this wasn't unified into a new column.
5. **Contact**: defined (name/email/phone/role + `LinkableMixin`) but never
   referenced by any service, capability, or seed data — a structural
   placeholder, same status as the HR/Marketing/Supply Chain domains
   `docs/ARCHITECTURE.md` already documents as deferred. Left as-is: adding
   relationships or seed data for an entity nothing consumes would be
   exactly the "theoretically useful" relationship the brief said not to add.
6. **Capabilities' entity id usage**: `read_supplier`/`read_product`/
   `read_customer`/`read_transactions` all take typed `uuid.UUID` ids
   matching the actual FK columns and query the Data Core directly (never
   through a cached or duplicated id) — consistent, no gap found.
7. **Schemas vs models**: `RiskRead`/`OpportunityRead`/`TaskRead`
   (Pydantic, `from_attributes=True`) match their ORM models field-for-field
   — no drift found.
8. **SQLite foreign key enforcement**: `PRAGMA foreign_keys` is not enabled
   (already documented in `docs/ARCHITECTURE.md`'s SQLite→PostgreSQL
   migration notes as a known, deferred difference) — this step did not
   change that, but added `test_seed_data_has_no_orphaned_foreign_keys`,
   which checks the *actual* seeded dataset for orphaned references rather
   than relying on the database to enforce it.

## What was deliberately not changed

- **No new column on `EventLogEntry`.** Unifying "which entity does this
  event concern" under one structured field would have meant either
  extending `BusinessEvent` with new optional fields and touching every
  existing publisher across Observation/Interpretation/Decision/
  Intelligence/Actions (real surgery across five modules this step was
  explicitly told not to modify unnecessarily), or guessing at a payload
  convention generically (risking silently wrong matches). The existing
  per-event-type payload convention already works for every real consumer;
  `app.core.entity_context.get_entity_context`'s own event lookup reuses the
  exact same "scan payload values for a matching id string" pattern
  `app.snapshot.service._recurrence_count` already established, rather than
  inventing a new mechanism. See `brain/decisions.md`.
- **No FK enforcement enabled in SQLite.** Already a documented, deferred
  difference for the eventual PostgreSQL migration; flipping it on now,
  untested against years of accumulated seed/test fixtures, was judged
  higher-risk than valuable for this step's actual goal (verifying today's
  data is coherent, not policing future writes).
- **No changes to Observation, Interpretation, Decision, the AI
  Orchestrator, or Home.** All five were re-run end-to-end against the
  fixed Data Core (`tests/test_data_core_pipeline_regression.py`) and
  produce byte-for-byte the same classification, options and
  recommendations as before this step.

## `app.core.entity_context.get_entity_context`: the one new read

A single function, `get_entity_context(session, entity_type, entity_id)`,
answering "what's directly around this Supplier/Product/Customer?" — its own
attributes, its directly related entities (Products for a Supplier,
Supplier for a Product, Transactions for any of the three), any open
Risks/Opportunities/Tasks pointing at it, any linked Documents/
Communications, and any Business Events that mention it. Returns
`{"found": False, ...}` for an unknown id or an entity type this Data Core
doesn't model relationships for (`company`, `transaction`) — never raises.

This is **plain structural reads only** — no Baseline, no Significance, no
Interpretation, no LLM, no scoring, exactly the brief's "ne doit PAS devenir
un nouveau moteur d'IA" constraint. It was added because the audit found
that Interpretation's context assembly, the AI Orchestrator's entity
resolution, and Home's Snapshot re-hydration had each already grown their
own bespoke way to answer a narrower version of this same question — this
is the one, generic, Data-Core-level version, available for a future caller
that needs it without going through the AI capability registry.

**It does not replace any existing code path.** `_resolve_entity_by_ref`,
`_dispatch_targeted_capabilities`, `app.interpretation.context.assemble_context`
and `app.snapshot.service.build_snapshot` are all untouched and still do
their own thing — this step's brief was explicit that Observation/
Interpretation/Decision/Orchestrator/Home should not be modified
unnecessarily, and none of them currently need `get_entity_context` to
function. Verified real, working data with the actual seeded dataset:
`get_entity_context` for "Steel Frame Assembly" correctly returns its
supplier (Northline Steel), 10 transactions, its one open Risk, and 6
related Business Events (`ObservationDetected`, `EventInterpreted`,
`DecisionProposed`, and the reactive Risk/Task events) — the concrete
"Product → Supplier → Transactions → Event → Risk/Opportunity/Decision"
chain the brief asked the Data Core to support.

## What is NOT stored in the Data Core

- Baseline, Significance, Interpretation, Decision — all computed fresh on
  read from Data Core rows and the Event Log, never persisted as their own
  tables (see `brain/business_state.md`, `brain/interpretation_engine.md`,
  `brain/decision_intelligence.md`).
- The Business State Snapshot — assembled on demand, not cached.
- Any vector embeddings, RAG index, or ML model state — none exist in this
  system.

## How the Intelligence layers consume the Data Core

Every layer above the Data Core reads it the same two ways, never a third:

1. **Direct filtered queries** (`session.query(Transaction).filter(...)`) —
   used throughout `app.core.analytics`, every `read_*` capability, and now
   `get_entity_context`. This is the primary, most common path.
2. **The Event Log, scanned by payload** — used by every idempotence/
   recurrence check (`_recurrence_count`, `_already_interpreted`,
   `_already_decided`, `get_entity_context`'s own event lookup) since the
   Event Log has no structured entity link (see above).

No layer holds a second, cached copy of Data Core data across requests; the
Business State Snapshot, Interpretation and Decision are all rebuilt from
these two read paths on every call.

## Limits of the Data Core MVP

- **No native cross-table foreign key for `LinkableMixin` entities** —
  application-level integrity only (documented since step 1,
  `docs/ARCHITECTURE.md`). A future evolution (a single `entities` registry
  table, or per-target join tables) is named there, not attempted here.
- **No FK enforcement in SQLite** — orphaned rows are structurally possible
  even though none exist in practice today (verified by this step's own
  orphan test against the real seed data).
- **`EventLogEntry` has no structured entity link** — entity-scoped event
  queries rely on a per-event-type payload convention plus a generic
  string-match fallback, not a queryable column.
- **`Contact` remains an unused structural placeholder**, same status as
  the HR/Marketing/Supply Chain domains.
- **Money is `Float`, not `Numeric`** — acceptable for MVP demo data,
  flagged since step 2 as a real-money-handling gap for later.
