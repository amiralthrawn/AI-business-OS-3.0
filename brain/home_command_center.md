# Home / Command Center

This document covers turning Home into the OS's real synthesis layer — the
step locked in when this work was opened: Home must answer **"what deserves
my attention now?"** by consuming every existing intelligence layer, without
becoming a new one itself.

## The chain

```text
DATA / EVENTS
      ↓
EXISTING INTELLIGENCE LAYERS (Observation, Interpretation, Decision Intelligence,
                               the older per-metric Risk/Opportunity rules)
      ↓
BUSINESS STATE SNAPSHOT (app.snapshot -- unchanged)
      ↓
HOME / COMMAND CENTER (app.home -- this step)
```

Home owns no intelligence of its own. Every number, classification,
explanation, recommendation and option it shows was already computed by an
earlier layer; Home's only job is to read, re-hydrate and present it —
verified explicitly by
`test_ai_priorities_match_the_snapshots_own_material_areas_exactly`, which
computes `build_snapshot()` independently and asserts Home's own output
matches it field-for-field.

## `GET /home` is already the Command Center endpoint

The brief's own conceptual example proposed `GET /home/command-center`. This
project already had a `GET /home` endpoint whose method was even already
named `get_command_center_view` — it just didn't yet expose AI Priorities,
Decisions or link back to detail pages. Rather than stand up a second,
parallel endpoint, `HomeService.get_command_center_view` was renamed to
`get_command_center` and enriched in place. `GET /home` **is** the Command
Center endpoint; no `/home/command-center` route was added.

## The seven MVP sections and where each one's data actually comes from

| Section | Source | New in this step? |
|---|---|---|
| AI Priorities | `build_snapshot(session, company_id).material_areas` | New (`get_ai_priorities`) |
| Risks | `HomeService.get_risks_summary` (open Risk rows) | Unchanged |
| Opportunities | `HomeService.get_opportunities_summary` (open Opportunity rows) | Unchanged |
| Decisions | `EventLogEntry` rows with `event_type="DecisionProposed"` | New (`get_decisions`) |
| Actions (pending validation) | `HomeService.get_tasks_summary` (`Task.status == PENDING_VALIDATION`) | Unchanged |
| Recent Activity | `HomeService.get_recent_events` (`EventLogEntry`, most recent first) | Unchanged |
| Ask AI | `POST /ai/ask` (`AIOrchestrator`, unchanged) | Unchanged backend; new inline frontend entry point |

## AI Priorities: re-exposing the Snapshot, not a second ranking

`HomeService.get_ai_priorities(company_id)` calls `app.snapshot.service.build_snapshot`
and maps its `material_areas` directly into a Home-shaped dict — `kind`,
`domain`, `title`, `impact`/`urgency`/`confidence` (straight from each area's
own `Significance`), and, for `interpretation`/`decision` kinds,
`interpretation_type`, `explanation`, `recommendation` and
`decision_options`. Nothing is recomputed; nothing is re-ranked beyond the
ordering `material_areas` itself already provides (urgency-then-impact).

This intentionally sits **alongside**, not on top of, the older
`HomeService.get_priorities()` method (severity-only, Risk/Opportunity only)
that the `list_priorities` AI capability still uses unmodified. The two
answer a similar-sounding question with genuinely different data shapes for
genuinely different consumers: `list_priorities` needs a stable, simple
shape an LLM prompt has used since step 9; the Command Center's "AI
Priorities" needs the full richness the Snapshot has grown since steps
14–17. Unifying them was judged out of scope and unnecessary risk for this
step — see `brain/decisions.md`.

## Linking back to an existing detail page, without changing `SnapshotArea`

A `risk`/`opportunity`-kind `SnapshotArea` carries the *related* entity
(e.g. a Product) but not the Risk/Opportunity row's own id — there was
never a reason for the Snapshot to carry that before this step. Rather than
add a field to `SnapshotArea` (touching three prior steps' worth of tests
for a Home-only concern), `get_ai_priorities` builds a small
`(entity_type, entity_id) -> row.id` lookup from the same open Risk/
Opportunity query `get_risks_summary`/`get_opportunities_summary` already
run, and matches each area against it. `detail_kind`/`detail_id` are `None`
whenever no such row exists (e.g. a `decision`-kind area for an entity with
no Risk/Opportunity yet) — an honest absence, never a broken or invented
link.

## Decisions: read straight from the Event Log

`HomeService.get_decisions()` queries `EventLogEntry` for
`DecisionProposed` entries, most recent first, and returns each payload's
`type`, `problem`, `options`, `recommendation` and `confidence` verbatim —
the exact same values `app.decision.engine` published. This mirrors exactly
how `get_recent_events()` already worked: Home reading the Event Log
directly rather than introducing a second persisted representation of a
Decision.

## No automatic execution from Home

Home has no method that changes a Task's status, approves anything, or
calls `ActionExecutor`. The "Actions requiring attention" section lists
`PENDING_VALIDATION` Tasks and, on the frontend, embeds the existing
`TaskActionButtons` component (already built for the Risk/Opportunity detail
pages) so a human can approve/reject inline — through the same, unmodified
`POST /actions/tasks/{id}/approve|reject` endpoints. Verified by
`test_pending_tasks_are_exposed_and_home_never_executes_them`: reading the
Command Center repeatedly never changes a Task's status, and `HomeService`
has no `approve_task`/`execute_task` method at all.

## Empty / insufficient context, explicit rather than guessed

Two distinct empty states, both tested:

- **No Company at all** (a brand-new, unseeded install):
  `get_command_center(company_id=None)` returns `priorities: []` without
  attempting to build a Snapshot (which needs a `company_id`) — an explicit
  skip, not an error.
- **A Company with no signals yet**: every section's query naturally
  returns empty/zero (no open Risks, no `DecisionProposed` events, no
  pending Tasks) — the existing, already-correct behavior of every
  underlying service method, not a new code path.

## Frontend: Home reflects the Command Center role, still MVP

`frontend/app/page.tsx` was restructured into exactly the seven sections
above, reusing existing components (`StatTile`, `TaskActionButtons`) and
styling conventions. The one new component, `components/HomeAskAI.tsx`, is
a compact version of the existing `/ai/ask-ai` page's form+result UI,
calling the same `askAI`/`approveTask`/`rejectTask` functions in
`lib/api.ts` — not a second chat system, the same Orchestrator entry point
embedded in a second place. The dedicated `/ai/ask-ai` page itself is
unchanged.

## What was verified end-to-end (not just unit tests)

Ran against a freshly rebuilt seeded database (`data/seed.py`, unchanged by
this step — already producing the full Observation → Interpretation →
Decision chain from steps 15–17):

```text
GET /home
  priorities: 6 areas (4 risk, 1 opportunity, 1 decision/insight for
    Coastal Metal Supply) -- each risk/opportunity area correctly links to
    its real Risk/Opportunity row id; the Coastal insight correctly has no
    detail link (none exists for that kind yet).
  risks: 4 total   opportunities: 1 total
  decisions: 5 (3 risk, 1 opportunity, 1 insight), each with real options/
    recommendation/confidence matching what app.decision produced.
  tasks: 4 pending_validation
  recent_events: 10 most recent Event Log entries, including DecisionProposed.

POST /ai/ask {"question": "What deserves my attention today?"}
  agent: priorities, requires_human_validation: false -- unaffected by this step.

Reading GET /home three times in a row: pending_validation_tasks stayed at
4 throughout -- no side effect from reading the Command Center.
```

## What's deferred (explicitly, not by omission)

- **No unification of `get_priorities` and `get_ai_priorities`.** Two
  methods, two consumers, two shapes, deliberately kept separate this step
  (see `brain/decisions.md`).
- **No notifications, no advanced personalization, no new Business
  modules.** All explicitly out of scope per the brief.
- **No detail page yet for `decision`/`observation`/`interpretation` kinds.**
  `detail_kind`/`detail_id` are `None` for these today; a future step could
  add a dedicated Decision detail view and extend the lookup accordingly,
  without changing the mechanism itself.
- **Decisions section has no "resolved" state.** A Decision is a stateless,
  point-in-time artifact (see `brain/decision_intelligence.md`); Home shows
  the most recent N regardless of whether their resulting Task (if any) was
  later approved or rejected. Cross-referencing that is future work.
