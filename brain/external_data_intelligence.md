# External Data Intelligence (Step 22)

This document covers connecting the External Connectivity Layer (Step 21:
Communication, Document, Contact) to the existing Intelligence chain
(Observation → Business Event → Interpretation → Decision → Action), so
external data can be detected, understood, decided on and acted on through
exactly the same mechanisms internal Data Core signals already use.

```text
External Data (Communication/Document/Contact)
      ↓
Observation (2 new, generic Observables)
      ↓
Business Event (ObservationDetected -- unchanged event type/shape)
      ↓
Interpretation (unchanged engine, now sees message content via `extra_context`)
      ↓
Decision Intelligence (unchanged options/recommendation logic)
      ↓
Action Proposal (2 new pending_action branches, domain-based)
      ↓
Human Validation (unchanged ActionExecutor)
      ↓
External Action (Mock Calendar / Mock Email, via app.connectors)
```

**Everything reused, nothing rebuilt**: no new detection engine, no new
Event type, no new classification logic, no new Decision options logic, no
new Action system, no new agent, no LLM inside a connector. Every numbered
section below names exactly what changed and why it was the minimal change
needed — see decision entries in `brain/decisions.md` for the two real
architectural calls this step made.

## Audit: how external data reaches the existing engines

- **`Communication`** (channel, direction, occurred_at, `related_entity_type`/`id`,
  `source`/`external_id` since step 21) is the one Data Core row every
  external signal in this step reads. No second copy, no new table.
- **`Contact`** resolves (or doesn't) an external identity to a Supplier/
  Customer — unchanged since step 21. This step never touches Contact rows.
- **The Observation Registry/Engine** (`app.observation`) already generically
  iterates any registered `Observable` against real Supplier/Product/
  Customer rows — the new Observables below register into it exactly like
  the three from steps 15/16, no engine rewrite.
- **Interpretation's context assembly** (`app.interpretation.context`)
  already builds a compact dict from a Business Event's payload; it needed
  one small, generic addition (see "Interpretation sees the message" below).
- **Decision Intelligence's option catalogs** already have `procurement` and
  `sales` domain entries (from step 17) — the new Observables use those
  exact same two domains, so **zero changes to option generation** were
  needed at all.
- **`get_entity_context`** (step 20) already includes `communications` for a
  Supplier/Customer — Cas B and Cas C below needed no new code, only tests.

## New Observables (2, not 6)

The brief suggested up to six example Observables. Only two were actually
built, both generic and reused across the same Baseline/Significance
machinery as the original three:

| Observable | Entity type | Domain | What it measures |
|---|---|---|---|
| `supplier_unanswered_message_age_days` | SUPPLIER | procurement | Age in days of the oldest still-unanswered inbound Communication linked to this supplier |
| `customer_unanswered_message_age_days` | CUSTOMER | sales | Same, for a customer |

**Why not the other four** (`external_inquiry_count`, `supplier_communication_activity`,
`customer_communication_activity`, `calendar_conflict_count`): each would
have needed either a company-wide entity type the Observation Engine
doesn't iterate today (no natural per-Supplier/Customer/Product fit), or an
ambiguous-direction metric that can only ever classify as `observation`
(useful, but not needed to demonstrate the three mandatory cases) — see
decision entry in `brain/decisions.md`. Cas C (calendar) is demonstrated via
`get_entity_context` instead of a new Observable (see below), which already
fully answers "does this meeting concern a known entity?" without forcing
calendar conflicts into a numeric-metric shape they don't naturally have.

`compute_unanswered_message_age` (new, `app.core.analytics`, mirroring the
existing `compute_margin_trend`/`compute_supplier_delivery_performance`
style) defines "unanswered" deliberately simply: an inbound Communication is
answered as soon as *any* outbound Communication for the same entity
**already occurred** after it — no thread-matching, no NLP. A calendar event
merely *scheduled* for later does not count as having already answered
anything (a real bug caught while building the demo — see `brain/decisions.md`
for the fix and why it matters for the cross-domain correlation demo below).

`supplier_unanswered_message_baseline`/`customer_unanswered_message_baseline`
(new, `app.core.baseline`, mirroring `margin_baseline` etc.) wrap it: no
`observed_value` (a message's age is a point-in-time fact, same reasoning as
`customer_value_baseline`), falling back to a company-declared expectation
(`declared_baselines={"unanswered_message_age_days": 3}`, added to the seed's
Business Context) or the generic benchmark (`2.0` days) otherwise.

Both Observables register `direction="lower_is_better"` in
`app.interpretation.engine._METRIC_DIRECTION` — a longer-unanswered message
is a genuinely universal "worse" fact, independent of the message's own
content, structurally identical to `delivery_delay_days`.

## Interpretation sees the message, not just a number

`app.interpretation.context.assemble_context` needed one small, generic
addition: `Observable` gained an optional `extra_context` callback (new
field, defaulting to `None` — every pre-existing Observable is unaffected),
called after `compute()` to attach one concrete record. For the two new
Observables, it's the actual unanswered Communication's subject and a body
excerpt. `assemble_context` surfaces this under `business_event.related_message`
(and, when the message-bearing Observable ended up as the *correlated* one
rather than the primary — see the cross-domain example below —
`related_messages_from_correlated_observations`). This is what makes the
LLM's narrative reference the actual email content instead of a bare
number, exactly the brief's own worked example.

**Nothing else about Interpretation changed.** Classification (`classify()`)
is unchanged; the LLM still never modifies the Data Core, Observation,
Baseline, Significance or the source Communication.

## Cas A — Supplier + Email (verified with real seed data)

Northline Steel's real, aged (8+ days), never-answered renegotiation email
(`data/seed.py`'s Mock Email dataset) produces a real, material Observation.
Because Northline Steel is *also* Steel Frame Assembly's supplier — and
that product already has a real, material `margin_pct` anomaly — the
**existing, unmodified** cross-domain correlation (`app.observation.engine._correlate`,
built in step 15) automatically merges them into ONE Business Event:

```text
GET the real Interpretation for Steel Frame Assembly (verified live):
  type: risk
  correlated_observations: [supplier_unanswered_message_age_days on Northline Steel]
  related_messages_from_correlated_observations: [{
    "message_subject": "Steel pricing renegotiation",
    "message_excerpt": "Hello, given recent raw material costs we would
      like to schedule a call to renegotiate pricing on the Steel Frame
      Assembly line for next quarter."
  }]
```

No new correlation code was needed — the exact mechanism from step 15
already generalizes to "a supplier's own external-communication signal"
exactly as well as "a supplier's own delivery-performance signal."

## Cas B — Website + Customer/Prospect

- **Known customer**: `web_004` (Alex Renner, `alex.renner@metrolinecorp.example`,
  company "Metroline Corp") resolves to the real Metroline Corp Customer row
  (step 21's own resolution, unchanged) — its Communication is visible via
  `get_entity_context(CUSTOMER, metroline.id)["communications"]`.
- **Unknown prospect**: `web_001` (Dana Whitfield, Brookfield Industrial)
  correctly stays unresolved — `related_entity_type`/`id` both `None`, no
  Customer ever created. Verified explicitly:
  `test_cas_b_website_inquiry_from_an_unknown_prospect_never_creates_a_customer`
  also confirms **no Observation is ever produced** for an unresolved
  contact — a deliberate, correct absence, not a bug: the Observation
  Engine iterates real Supplier/Customer rows, and there is no row to
  attach Significance to for a prospect that was never resolved to one.
  This is the same "never force a classification the data doesn't support"
  principle from Interpretation (steps 16–17), now extended one layer
  further down to Observation itself.

## Cas C — Calendar + Business Context

No new Observable. `calendar_003` ("Northline Steel pricing call", ingested
by step 21's `ingest_calendar`, unchanged) already resolves to the real
Northline Steel Supplier and already appears in
`get_entity_context(SUPPLIER, northline.id)["communications"]` — this step
only added a test proving it, since the mechanism already existed. Building
a dedicated `calendar_conflict_count` Observable was considered and
deliberately not built (see "New Observables" above and `brain/decisions.md`):
conflicts are pairwise between events, not a property of one Supplier/
Customer, so forcing them into the per-entity Observable shape would have
been exactly the kind of scenario-specific over-fitting the brief warned
against.

## Cross-domain reasoning (verified live)

`POST /ai/ask {"question": "Why is Northline Steel important for our margin?"}`
matches the existing "margin" topic (finance + procurement + sales agents,
unchanged since step 12/18), resolves Northline Steel as a Supplier, and
dispatches `read_supplier`, `read_transactions` and `analyze_supplier_performance`
— real, existing capabilities, consulted because the question named a
supplier that now also carries an external-communication signal. No new
capability was added; the Orchestrator's own step-12/18 machinery already
generalizes to an entity enriched by external data without any changes.

## Decision Intelligence and Action Proposal: one domain-based branch

Decision Intelligence's option catalogs already had `procurement`/`sales`
entries — the new Observables use exactly those two domains, so **no
changes to option generation were needed**. The one real addition:
`app.decision.engine._pending_action_for(decision)` inspects
`decision.data_used[0]["observable"]` (already-existing data, not a new
field) and, **only when the primary signal came from one of the two new
external Observables**, chooses a connector-aware `pending_action` instead
of the plain `"create_task"`:

| Domain | `pending_action` | On approval |
|---|---|---|
| procurement | `connector_followup_meeting` | `MockCalendarProvider.create_event(...)` |
| sales | `connector_followup_email` | `MockEmailProvider.send_message(...)` |

Every internal-metric decision (`margin_pct`, `delivery_delay_days`,
`customer_revenue_variation_pct`) keeps proposing the plain `"create_task"`
exactly as before step 22 — verified by every pre-existing Decision
Intelligence test passing unmodified.

`ActionExecutor._run` gained two branches (its own docstring already
documents this as the sanctioned extension point: "adding a new executable
action means adding a branch to `_run`"), and `ActionsService` gained one
new method, `finalize_connector_followup`, which re-resolves the target
Contact's email from the Task's own `related_entity_type`/`related_entity_id`
(the same pair Decision Intelligence used to propose it) rather than storing
new fields on `Task`. **No second action system**: the Task is still the
same `PENDING_VALIDATION` → `EXECUTED` row, approved through the same
`POST /actions/tasks/{id}/approve` endpoint, by the same `ActionExecutor`.

Verified live end-to-end: Coastal Metal Supply's real, unanswered,
unshadowed (no pre-existing Risk/Opportunity) email produced a
`connector_followup_meeting` Task; approving it created a real event in
`MockCalendarProvider` with `attendees=["dispatch@coastalmetalsupply.example"]`
— the exact Contact email resolved back in step 21's ingestion.

## Idempotence

Unchanged mechanisms, re-verified together: two `sync` calls never
duplicate a Communication (step 21's own unique `(source, external_id)`
index); two sweeps of Observation/Interpretation/Decision never duplicate
an Event Log entry or a Task (steps 15–17's own dedup checks). Tested
together in one sequence
(`test_two_syncs_then_two_sweeps_never_duplicate_anything`) to confirm the
two idempotence layers compose correctly, not just independently.

## What was verified end-to-end (not just unit tests)

Ran against a freshly migrated, seeded database:

```text
Seed applied: ... 7 observation events published, 7 interpreted
  ({'risk': 5, 'opportunity': 1, 'insight': 1, 'observation': 0}),
  7 decisions made (same distribution), 1 actions proposed.
  Connectors: 8 emails, 6 calendar events, 7 website inquiries ingested.
```

- Steel Frame Assembly's `margin_pct` Interpretation correctly includes
  Northline Steel's real email content via cross-domain correlation.
- BrightWorks Ltd's `customer_unanswered_message_age_days` Interpretation
  correctly includes its real delivery-complaint email content.
- `GET /entity context` for Metroline Corp and Northline Steel correctly
  surface their website/calendar-sourced Communications.
- `POST /ai/ask` "Why is Northline Steel important for our margin?" pulls
  in finance + procurement capabilities in one answer.
- Coastal Metal Supply's full loop reaches a real `PENDING_VALIDATION` Task;
  approving it creates a real Mock Calendar event with the correct attendee.
- Re-running the full chain a second time (`POST /connectors/*/sync` +
  Observation/Interpretation/Decision sweeps) changes nothing: 0 new
  Communications, 0 new Business Events, 0 new Interpretations/Decisions,
  0 new Tasks.

## What's deliberately out of scope

- **Only 2 of the brief's 6 suggested Observables were built** — the other
  four don't fit the per-entity Observable shape cleanly (company-wide
  counts, pairwise conflicts) or would only ever classify as `observation`;
  see `brain/decisions.md` for the full reasoning.
- **No Task from an unresolved prospect's inquiry, and no calendar-conflict
  action.** The brief's own diagrams mark these "éventuellement" (optional);
  not built here.
- **No real Gmail/Outlook/Google Calendar, no OAuth, no LLM inside a
  connector, no new agent, no RAG/vector DB/ML.** All explicitly out of
  scope per the brief, and none were added.
- **"Unanswered" is a coarse proxy** (no thread/conversation id matching) —
  documented in `compute_unanswered_message_age`'s own docstring as a real,
  accepted MVP limitation, not a design ambition.
- **Metroline Corp's own website inquiry doesn't always materialize** in the
  full seed dataset: an unrelated, later outbound Communication (an invoice)
  happens to "answer" it under this step's simple proxy definition — a real
  consequence of overlapping realistic timelines, not a bug, and not forced
  to materialize artificially.
