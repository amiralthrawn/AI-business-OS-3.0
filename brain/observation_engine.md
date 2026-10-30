# Business Observation Engine

This document covers the first generic, cross-domain discovery layer, sitting
between the Data Core and the existing per-metric Intelligence rules from
steps 12–14. It answers the question locked in when this step was opened: how
does the system notice something significant is happening without a
hand-written `if` branch per event type?

## The three concepts, kept explicitly separate

```text
Observable  = ce qu'on mesure     (what's measured — a named, registered metric)
Observation = ce qu'on constate   (what's found for one entity, normal or anomalous)
Business Event = un phénomène métier significatif (an anomaly worth recording)
```

An anomalous Observation is **not automatically a Risk or an Opportunity**.
This engine stops at publishing `ObservationDetected` on the Event Bus/Event
Log. Turning a Business Event into a Risk/Opportunity/Insight is a later,
separate interpretation step this engine does not perform — the existing
per-metric rules in `app.intelligence.risks.service` /
`app.intelligence.opportunities` still own that judgment call for now (see
"What's deferred" below).

## The chain

```text
DATA CORE
   ↓
OBSERVABLE REGISTRY      (app.observation.registry — pluggable metric definitions)
   ↓
OBSERVATION ENGINE       (app.observation.engine — compute, compare, correlate)
   ↓
BUSINESS EVENTS          (ObservationDetected, on the existing Event Bus/Event Log)
   ↓
SIGNIFICANCE + BUSINESS CONTEXT   (reused, not duplicated)
   ↓
BUSINESS STATE SNAPSHOT  (app.snapshot — now fed by both Risks/Opportunities AND raw Observations)
   ↓
AI ORCHESTRATOR
```

## Observable Registry (`app/observation/registry.py`)

An `Observable` is a named, registered signal: which metric, which kind of
entity it applies to, which existing Baseline-producing function computes it
(`compute: (Session, entity_id, BusinessContext) -> (Baseline, current_value)`,
the exact same shape `app.core.baseline`'s three helpers already have), and
the `(medium, high)` impact thresholds Significance should use for it.

`ObservableRegistry` mirrors `app.ai.capabilities.registry.CapabilityRegistry`
on purpose — register once, look up by name, list them all. Adding a new
Observable (a new metric, a new domain) means registering one more entry in
`build_observable_registry()` (`app/observation/__init__.py`); it never
requires touching `app.observation.engine`, which has no per-metric branch
anywhere in it.

The MVP registers exactly three Observables, reusing the three Baseline
helpers built in the previous step — no new computation:

| Observable | Domain | Entity | Reuses |
|---|---|---|---|
| `margin_pct` | finance | Product | `margin_baseline` |
| `delivery_delay_days` | procurement | Supplier | `supplier_delivery_baseline` |
| `customer_revenue_variation_pct` | sales | Customer | `customer_value_baseline` |

**Gotcha caught and fixed**: `ObservableRegistry` defines a method named
`list`, which shadows the builtin `list` for every type annotation written
afterwards in the same class body (e.g. `for_entity_type(...) -> list[Observable]`)
once Python evaluates that annotation against the class's own namespace. Fixed
with `from __future__ import annotations` at the top of the module, which
defers annotation evaluation entirely.

## Observation computation (`app/observation/engine.py`)

`compute_observation` calls the Observable's own `compute` to get a `Baseline`
+ current value (reusing `app.core.baseline`, never a parallel calculation),
counts real recurrences from the Event Log, and calls
`assess_significance` (reusing `app.core.significance` unchanged) to classify
the deviation. The result is an `Observation` — a plain record, not yet a
business phenomenon — whose `is_anomalous` property is just
`significance.is_material`, the same one small readable rule the rest of the
system already uses.

## Cross-domain correlation

`_correlate` groups anomalous Observations that describe the same underlying
phenomenon before publishing. For this MVP, exactly **one real link** is
followed: a Product and its own Supplier (`product.supplier_id`) — e.g. a
supplier's delivery trouble and that supplier's product's margin trouble are
merged into a single Business Event instead of two unrelated ones. This is a
real, tested mechanism (`test_sweep_correlates_a_products_margin_issue_with_its_own_supplier`),
not a general graph search — deliberately narrow rather than over-built.

The seeded demo dataset does not happen to trigger this path (Chain 1's
margin issue and Chain 2's delivery issue involve two different
supplier/product pairs, by original design from step 12's dataset) — the
correlation is proven by the unit test, not by the demo run. See "What's
deferred" for what a real graph-based correlation would need.

## Sweep, publication, idempotence (`run_observation_sweep`)

The one entry point: computes every registered Observable for every matching
entity of the company, filters to anomalies, correlates them, and publishes
one `BusinessEvent(event_type="ObservationDetected", source="observation_engine")`
per resulting cluster — skipping any `(observable, entity)` pair that was
already published in a previous sweep (checked via a Python-side scan of
existing `EventLogEntry` rows, the same acceptable-at-this-scale pattern
`app.snapshot` already uses for recurrence counting). Running the sweep twice
in a row publishes zero new events the second time.

No scheduler exists yet (same decision as `app.intelligence.monitoring` from
step 12) — `POST /observation/sweep` is a manual trigger.

## Snapshot integration — "progressively fed by Business Events"

`build_snapshot()` (`app/snapshot/service.py`) now does two things instead of
one:

1. Builds a `SnapshotArea` for every open Risk/Opportunity, exactly as before
   (`_build_area_for_risk` / `_build_area_for_opportunity`).
2. Additionally scans the Event Log for `ObservationDetected` entries and adds
   a `SnapshotArea(kind="observation")` for each one **whose entity isn't
   already covered by an open Risk/Opportunity** — `_build_area_for_observation`
   re-hydrates the area directly from the event's payload (the Observation
   Engine already did the Baseline/Significance work when it published the
   event), no recomputation.

This is the literal mechanism for "the Snapshot must progressively be fed by
Business Events instead of depending only on already-created
Risks/Opportunities": today, on this dataset, every anomaly the Observation
Engine finds is also caught by the older per-metric rules, so every area
still shows up as `kind="risk"`/`"opportunity"` (the more specific,
already-actioned representation wins, proven by
`test_snapshot_does_not_duplicate_an_observation_already_covered_by_a_risk`).
The `kind="observation"` path exists and is tested
(`test_snapshot_includes_an_observation_area_not_covered_by_an_existing_risk`)
for the moment a future Observable has no corresponding per-metric rule yet —
which is exactly the point: new signals can reach the Snapshot the day
they're registered, without waiting for someone to also write a dedicated
Risk-detection rule for them.

## What was verified end-to-end (not just unit tests)

Ran against the real seeded dataset (`data/seed.py`, now also calling
`run_observation_sweep` after the existing `run_monitoring_sweep`):

- Seed run: `4 observation events published` — one per real anomaly in the
  dataset (Steel Frame Assembly margin, Iberia Logistics Parts delivery,
  BrightWorks Ltd decline, Metroline Corp growth).
- Re-running `POST /observation/sweep` immediately after: `anomalies_detected: 4`,
  `business_events_published: 0` — confirmed idempotent against a real
  database, not just the in-memory test fixtures.
- Direct inspection of the `events` table: all 4 `ObservationDetected` rows
  present with `source="observation_engine"` and the expected payload fields.
- `POST /ai/ask` with "What deserves my attention today?" still resolves
  correctly through `list_priorities` + `get_business_state_snapshot` +
  targeted capability drill-down — confirming the new Event Log writes and
  the modified `build_snapshot()` didn't disturb the step-14 flow.

## What's deferred (explicitly, not by omission)

- **Business Event → Risk/Opportunity/Insight promotion is not built.** The
  target architecture's own diagram places this as a later step; this engine
  intentionally stops at "a significant phenomenon was detected," leaving the
  older per-metric rules as the only current path to an actual Risk/Opportunity.
  Unifying the two (so a registered Observable's anomaly can itself become a
  Risk, without a hand-written detection rule) is the natural next step, not
  done here to avoid conflating discovery with interpretation in one change.
- **Correlation is one real edge, not a graph.** Only Product↔its own
  Supplier is followed. A general "find any linked entities with concurrent
  anomalies" search is future work.
- **No LLM involvement anywhere in detection.** Exactly as required — the
  engine is deterministic Python; an LLM would only ever explain an already-
  published Business Event, never decide whether one exists.
- **No new Data Core, no new monitoring loop.** Observables read the same
  Data Core tables `app.core.analytics` already reads; the sweep is a plain
  function call, not a background process or scheduler.
