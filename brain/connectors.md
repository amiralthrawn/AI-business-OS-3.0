# External Connectivity Layer (Step 21)

This document covers the first External Connectivity Layer built for the
Business OS: a Connector/Provider abstraction with Mock Providers for
Email, Calendar and Website inquiries, and the Ingestion/Mapping layer that
turns their normalized output into Data Core rows. **No real external
service is connected** — no OAuth, no Gmail/Outlook/Google Calendar, no
personal data. Everything is realistic, static, in-memory mock data.

## The chain

```text
EXTERNAL SYSTEM (a real Gmail/Outlook/Calendar/website form, later)
      ↓
CONNECTOR (a Provider: MockEmailProvider today)
      ↓
NORMALIZED EXTERNAL OBJECT (ExternalEmail / ExternalCalendarEvent / WebsiteInquiry)
      ↓
INGESTION / MAPPING (app.connectors.ingestion)
      ↓
DATA CORE (Communication, Document, Contact)
      ↓
Business / Intelligence / AI (unchanged, does not yet read this data)
```

## What the pre-implementation audit found

- **`Contact`** existed since step 1 but was never used anywhere — no
  service, capability, or seed data referenced it (confirmed by step 20's
  own audit, `brain/data_core.md`). It also had no `company_id`, unlike
  every other Data Core entity.
- **`Communication`/`Document`** already had `LinkableMixin`
  (`related_entity_type`/`related_entity_id`) and were already used
  (minimally, for flavor) in `data/seed.py` — the right target entities for
  ingested emails/calendar events/website inquiries, needing only a
  provenance field, not a new entity.
- **No existing ingestion abstraction** existed to reuse or duplicate — this
  is genuinely new infrastructure, not a rebuild of something already there.
- **No column existed anywhere to record where an imported record came
  from** — every entity in the Data Core was, until now, either
  authored directly (seed, API) or produced by an internal pipeline
  (Observation/Interpretation/Decision, tracked via the Event Log). This
  step is the first time the Data Core needs to remember "this row came
  from an external system, identified by its own id."

## Schema changes (the only Data Core changes this step made)

Three small, additive, nullable-everywhere-it-can-be changes (migration
`6baa8061c9ed`):

1. **`Contact.company_id`** (new, `NOT NULL`, FK `companies.id`) — Contact
   went from an unused placeholder to an entity ingestion actually writes,
   so it needed the same company-scoping every other entity already has.
2. **`Communication.source` / `Communication.external_id`** (both nullable
   strings, unique together) — provenance: `source="mock_email"`,
   `external_id="email_001"`. `None`/`None` for a Communication created
   directly (e.g. the seed script's own two demonstrative rows predating
   connectors) — provenance is additive, not retrofitted onto old data.
3. **`Document.source` / `Document.external_id`** — same convention, for
   email attachments ingested alongside their Communication.

The unique index on `(source, external_id)` is what makes ingestion
idempotent at the database level, not just in application logic: a second
`INSERT` for the same external item would violate the constraint before the
application-level `_already_ingested` check even needs to matter in a
concurrent-write scenario (single-process MVP today, but the constraint
costs nothing and pays for real concurrency later).

**No changes to Observation, Interpretation, Decision, the AI Orchestrator,
Home, or any Business/Intelligence table.** None of them read `Communication`
or `Contact` today, so none of them can be affected by this step, and the
step's own pipeline-compatibility test
(`tests/test_connectors_pipeline_compatibility.py`) proves it: ingesting all
three connectors on top of the fully seeded dataset produces byte-for-byte
the same Observation/Interpretation/Decision/Orchestrator/Home results.

## Module layout

```text
app/connectors/
    __init__.py
    base.py         SyncResult (the one uniform sync response shape)
    models.py       ExternalEmail, ExternalCalendarEvent, WebsiteInquiry (normalized objects)
    registry.py     ConnectorRegistry, build_connector_registry(), connector_registry
    ingestion.py    _resolve_contact, _match_known_entity, ingest_email/calendar/website, sync_connector
    router.py       GET /connectors, GET/POST /connectors/{type}/status|sync
    email/
        base.py     EmailProvider (ABC)
        mock.py     MockEmailProvider
    calendar/
        base.py     CalendarProvider (ABC)
        mock.py     MockCalendarProvider
    website/
        base.py     WebsiteProvider (ABC)
        mock.py     MockWebsiteProvider
```

Each Provider is an `ABC` (matching `EventBus`/`LLMClient`'s existing style
in this codebase, not a new pattern) so a future `GmailProvider` or
`GoogleCalendarProvider` implements the exact same interface and is a
one-line change in `registry.py` — nothing above the Provider interface
(ingestion, the router) imports a concrete provider class directly.

## Providers contain no business intelligence

`MockEmailProvider`/`MockCalendarProvider`/`MockWebsiteProvider` only ever
return data and mutate their own in-memory state (`send_message`,
`create_event`/`update_event`/`cancel_event`, `mark_processed`) — they never
touch a `Session`, never classify anything, never decide anything.
`app.connectors.ingestion` is the *only* place that touches the Data Core,
and it is deliberately dumb: it maps fields across and resolves an identity,
nothing more. Classifying an imported email as urgent, deciding a website
inquiry is a real opportunity, or scheduling a meeting based on an email's
content are all things a *future* step could build on top of this data —
explicitly not attempted here, per the brief.

## Entity resolution: reliable-only, never invented

`_match_known_entity` (in `ingestion.py`) is the one place identity
resolution happens, for all three connectors:

1. Normalize the sender's email domain (`northlinesteel.com` → `northlinesteel`)
   and, for a Website inquiry, its stated company name.
2. Check whether that normalized candidate is a substring of (or contains)
   an existing Supplier's or Customer's own normalized name.
3. A candidate under 4 characters is never considered (avoids a short,
   coincidental match).
4. No match → the Contact is created **unresolved**
   (`related_entity_type`/`related_entity_id` both `None`) — a real, valid
   state, not an error.

**No Supplier, Customer or Opportunity is ever created by ingestion** — only
a `Contact`, which may itself remain unresolved. This is a hard rule: the
brief was explicit that identity must never be guessed into a new business
entity. Verified end-to-end against the real seeded dataset: `procurement@northlinesteel.com`
resolves to the real "Northline Steel" Supplier, `alex.renner@metrolinecorp.example`
(company: "Metroline Corp") resolves to the real Customer, while
`sales@thornfieldindustries.example` (an unseen prospect) and the spam
inquiry both stay unresolved.

`_resolve_contact` also **deduplicates by email within the company**: a
second message from `procurement@northlinesteel.com` (the seeded mock
mailbox has two — an initial email and a follow-up in the same thread)
reuses the exact same `Contact` row rather than creating a second one.

## Mapping to the Data Core

| Normalized object | Data Core target(s) |
|---|---|
| `ExternalEmail` | one `Communication` (`channel="email"`) + one `Document` per attachment (`document_type="email_attachment"`) |
| `ExternalCalendarEvent` | one `Communication` (`channel="calendar"`, direction always `OUTBOUND` — see below) |
| `WebsiteInquiry` | one `Communication` (`channel="website"`, direction `INBOUND`) |

`CommunicationDirection` is inbound/outbound, which fits an email or a
website inquiry naturally but not a calendar event (a meeting isn't
"sent" or "received"). Rather than add a third direction value for one
channel, calendar-sourced Communications always use `OUTBOUND` — an
arbitrary but consistent, documented convention ("the company's own
recorded activity"), not a claim about who initiated the meeting.

## Idempotence

Every ingestion function checks `(source, external_id)` against existing
`Communication` rows before creating anything; a match increments `skipped`
and does nothing else. Verified three ways: a unit test per connector
running ingestion twice in a row, an API-level test (`POST .../sync` twice),
and the real seeded database (`data/seed.py` ingests once at seed time;
`POST /connectors/{type}/sync` afterward against the live API returned
`created: 0, skipped: <fetched>` for all three connectors).

## API

- `GET /connectors` — every registered connector type with its live status.
- `GET /connectors/{type}/status` — `{"connector", "ingested_count", "last_ingested_at"}`, a plain count/max-date read against `Communication.source`, no new persistence.
- `POST /connectors/{type}/sync` — provider → fetch → normalize → ingest → `SyncResult` (`{"connector", "fetched", "created", "updated", "skipped"}`). `updated` is always `0` for the Mock Providers today (their data never changes between syncs) — kept in the shape for when a real provider can report actual edits.

## What was verified end-to-end (not just unit tests)

Ran against a freshly rebuilt, migrated, seeded database:

```text
Seed applied: ... Connectors: 7 emails, 6 calendar events, 7 website inquiries ingested.

GET /connectors
  email: ingested_count 7 | calendar: 6 | website: 7

POST /connectors/email/sync (again, live)   -> {"fetched":7,"created":0,"skipped":7}
POST /connectors/calendar/sync (again, live) -> {"fetched":6,"created":0,"skipped":6}
POST /connectors/website/sync (again, live)  -> {"fetched":7,"created":0,"skipped":7}
POST /connectors/sms/sync                    -> 404

Real Contact/Communication rows inspected directly:
  procurement@northlinesteel.com -> Contact resolved to Supplier "Northline Steel"
    (both email_001 and email_007 share this one Contact)
  ops@brightworks.co.uk          -> Contact resolved to Customer "BrightWorks Ltd"
  alex.renner@metrolinecorp.example (web_004) -> Contact resolved to Customer "Metroline Corp"
  sales@thornfieldindustries.example, spam sender, internal acme.example
    addresses -> all correctly left unresolved (related_entity_type=None)
```

Also confirmed the full Observation → Interpretation → Decision → AI
Orchestrator → Home chain produces identical results whether or not
connector ingestion has run alongside the seed — this layer is additive
only, never a second source of truth.

## What's deferred (explicitly, not by omission)

- **No real provider (Gmail, Outlook, Google Calendar) implemented.**
  Deliberately out of scope for this step; the interfaces
  (`EmailProvider`/`CalendarProvider`/`WebsiteProvider`) exist specifically
  so implementing one later is additive, not a rewrite.
- **No AI/Intelligence interpretation of connector data.** Nothing reads
  `Communication`/`Contact` rows from Observation, Interpretation, Decision
  or the AI Orchestrator yet — explicitly the next step, not this one.
- **`updated` is always 0.** The Mock Providers' data is static; a real
  provider that can report an edited message/event would need ingestion's
  matching logic extended to compare content, not just existence.
- **No Task created from a Website inquiry or a calendar conflict.** The
  brief's own diagrams say "éventuellement Task" for these — read as
  optional/future, not built here.
- **Calendar conflicts are surfaced by nothing yet.** `calendar_003`/
  `calendar_004`'s real overlap in the mock data exists to prove the
  `list_events`/`get_availability` interface handles it correctly (tested),
  not because anything currently acts on a detected conflict.
