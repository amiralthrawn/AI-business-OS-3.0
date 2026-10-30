# Step 24 — Frontend API contract (final backend audit)

Read-only audit of every HTTP endpoint the backend exposes, done before
starting the main frontend build. No architecture, agent, capability or
entity was touched. Zero backend fixes were needed: no problem found was
blocking for the frontend as currently scoped (Home, Data: Suppliers/
Customers/Products/Transactions, Business: Finance/Procurement/Sales,
Intelligence: Risks/Opportunities, Actions: Tasks, AI: Ask AI). Everything
below marked "reported" is a real, documented gap that does not stop that
build.

## Endpoints available, by frontend area

### Home (`/`)
- `GET /home` → `HomeResponse` (overview counts, AI priorities, risks/
  opportunities/tasks summaries, recent decisions, recent events). Already
  in production use since Step 8/19; unchanged.

### Data
| Page | Endpoint(s) |
|---|---|
| `/data/suppliers`, `/data/suppliers/[id]` | `GET /suppliers`, `GET /suppliers/{id}` |
| `/data/customers`, `/data/customers/[id]` | `GET /customers`, `GET /customers/{id}` |
| `/data/products`, `/data/products/[id]` | `GET /products`, `GET /products/{id}` |
| `/data/transactions` | `GET /transactions`, `GET /transactions/{id}` |
| `/data/contacts` (placeholder) | **none** — see Contacts gap below |
| `/data/documents` (placeholder) | **none** — Documents are only ever embedded inside a Supplier/Customer detail response (`documents: LinkedDocument[]`), never listable on their own |

Communications are exposed the same way as Documents: embedded in
Supplier/Customer detail (`communications: LinkedCommunication[]`), never
as a standalone list.

### Business
| Page | Endpoint |
|---|---|
| `/business/finance` | `GET /finance/overview` |
| `/business/procurement` | `GET /procurement/overview` |
| `/business/sales` | `GET /sales/overview` |

### Intelligence
| Page | Endpoint(s) |
|---|---|
| `/intelligence/risks`, `/intelligence/risks/[id]` | `GET /intelligence/risks`, `GET /intelligence/risks/{id}` |
| `/intelligence/opportunities`, `/intelligence/opportunities/[id]` | `GET /intelligence/opportunities`, `GET /intelligence/opportunities/{id}` |
| `/intelligence/decision-intelligence` (placeholder) | **none dedicated** — decisions are only readable via `GET /home`'s `decisions` field (last N `DecisionProposed` events, re-hydrated) |
| Business Events | **none dedicated** — only `GET /home`'s `recent_events` (last N, unfiltered) and each Supplier/Customer/Product detail's own `related_events` (entity-scoped, from `get_entity_context`) |
| Business Context / Snapshot | `GET /business-context`, `PATCH /business-context`, `GET /business-context/suggestions` — the Snapshot itself has no direct endpoint; it is only ever consumed internally (Home's AI priorities, Ask AI's cross-domain reasoning) |

Manual sweep triggers exist for completeness but are operational, not
frontend-facing: `POST /observation/sweep`, `POST /interpretation/sweep`,
`POST /decision/sweep`, `POST /intelligence/monitor`.

### Actions
| Page | Endpoint(s) |
|---|---|
| `/actions/tasks` | `GET /actions/tasks`, `GET /actions/tasks/{id}` |
| Approve / reject (HITL) | `POST /actions/tasks/{id}/approve`, `POST /actions/tasks/{id}/reject` |

"Action Proposals" are not a separate concept: a `Task` with
`pending_action` set (not `null`) *is* an AI-proposed action awaiting
validation, already exposed as a field on `TaskRead` and already used by
the frontend to decide whether to render `TaskActionButtons`.

### AI
| Page | Endpoint |
|---|---|
| `/ai/ask-ai` | `POST /ai/ask` → `AskAIResponse` (`answer`, `agent` — comma-joined when the Orchestrator's cross-domain routing selects more than one, `capabilities_used`, `context`, `requires_human_validation`, `action_result`) |

No dedicated introspection endpoint lists available Agents/Capabilities;
none is needed by the current Ask AI page (a single question/answer form).

### Connectors
| Purpose | Endpoint |
|---|---|
| List all connectors + status | `GET /connectors` |
| One connector's status | `GET /connectors/{type}/status` |
| Trigger a sync | `POST /connectors/{type}/sync` |

Functionally complete for a future Connectors page, but these three return
plain `dict` (no Pydantic `response_model`), unlike every other router in
the codebase — reported, not blocking (FastAPI still serves valid,
correctly-shaped JSON; there is simply no typed OpenAPI schema for it yet).

## Consistency check

- `RelatedEntityType`, `TaskStatus`, `RiskSeverity`/`RiskStatus`,
  `OpportunityStatus` enum values match `frontend/lib/types.ts` exactly —
  spot-checked field by field, no drift found.
- Every Pydantic response model using `from_attributes=True` is backed by
  an ORM row with matching field names; every hand-built dict response
  (the `app/data/service.py` and `app/domains/*/service.py` composition
  layers) was checked against its schema field-for-field.
- CORS (`allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+"`) covers
  both the frontend's server-side fetches and the Ask AI page's
  client-side fetch to a different port.

## Gaps found (all reported, none blocking)

1. **Contacts have no read API at all**, and are not even linked at the
   database level to a specific `Communication` row (`Communication` has
   no `contact_id` column) — only to a Supplier/Customer, via
   `Contact.related_entity_type`/`related_entity_id`. A Supplier/Customer
   detail page can show "3 communications" but never who sent them. This
   matches the frontend's own `/data/contacts` placeholder, which was
   never wired into the Step 23B sidebar — the gap is consistent on both
   sides, not a mismatch. Fixing it for real (linking a Communication to
   the Contact who sent it) is a schema change, correctly out of scope for
   an audit step that must not touch new entities or big features.
2. **Documents and Communications have no standalone list endpoint** —
   only reachable embedded inside a Supplier/Customer detail response.
   Sufficient for the current frontend scope (no dedicated Documents/
   Communications page is planned); would need a small
   `app/data/service.py` addition if one ever is.
3. **Decision Intelligence and Business Events have no dedicated
   endpoint** — both are readable only through `GET /home`'s bounded,
   unfiltered `decisions`/`recent_events` lists, or entity-scoped via
   `get_entity_context`'s `related_events`. The frontend's own
   `/intelligence/decision-intelligence` page is still a placeholder, so
   this isn't currently blocking anything; it would need a small
   dedicated read endpoint if that page is built out.
4. **No `/company` endpoint** — nothing exposes the actual seeded
   `Company.name` anywhere in any response. Cosmetic only: the Sidebar
   already shows a static "AI Business OS" title rather than the real
   company name, so no page is currently missing data because of this.
5. **`GET /actions/tasks`, `GET /intelligence/risks`, `GET
   /intelligence/opportunities` are not company-scoped** — they return
   every row in the table with no `company_id` filter, unlike every
   Business Domain router (which all do `db.query(Company).first()` then
   filter by its id). In the current single-company MVP (exactly one
   `Company` row ever exists) this produces identical results either way,
   so it is not a live bug — but it is a latent one, and the inconsistency
   itself is worth knowing about before any multi-tenancy work.
6. **Connectors endpoints return untyped `dict`**, not a Pydantic
   `response_model`, unlike every other router — no functional impact, just
   a documentation/discoverability gap in the generated OpenAPI schema.

## Verification

- `pytest -q`: **265 passed**, 0 failed, 0 skipped (unchanged from before
  this audit — no backend code was modified).
- `npm run build`: **clean**, 0 TypeScript errors.

## Conclusion

No blocking problem was found. The backend's current read surface exactly
covers what the sidebar-reachable frontend pages (Home, Data ×4,
Business ×3, Intelligence ×2, Actions, AI) need, with correct, consistent
shapes end to end. **The backend is ready to start the main frontend
build.** The six gaps above are legitimate future work, not defects to fix
before that build starts.
