# Business State: Baseline → Significance → Snapshot

This document covers the three layers built to answer the question locked in
after step 12: *how do Business Context, events and history produce a
representation of the company's current state that the AI can use without
loading everything into the LLM's context?*

## The chain

```text
DATA CORE + EVENT LOG
        +
BUSINESS CONTEXT (declared config, declared_baselines)
        ↓
     BASELINE            (app.core.baseline)
        ↓
   SIGNIFICANCE          (app.core.significance)
        ↓
BUSINESS STATE SNAPSHOT  (app.snapshot)
        ↓
   AI ORCHESTRATOR
        ↓
 targeted capabilities   (same ones a named question would use)
```

Each layer is a plain, deterministic Python module with no side effects
(except Snapshot, which reads). No LLM, no RAG, no embeddings, no vector
database, no persistent cache anywhere in this chain.

## Baseline (`app/core/baseline.py`)

Formalizes "what counts as normal for a metric" as one of three sources,
never conflated:

- **`observed_history`** — computed from `app.core.analytics`'s existing
  trend functions (the historical/earlier half of a baseline-vs-recent
  split), with a confidence level (`insufficient`/`low`/`medium`/`high`)
  derived purely from sample size.
- **`declared`** — a target the company itself stated in
  `BusinessContext.declared_baselines` (e.g. `{"margin_pct": 0.30}`).
  **Always takes precedence over observed history** when present, because a
  declared target is an intention, not a measurement, and the two must never
  be silently averaged or confused (this was an explicit requirement).
- **`generic_fallback`** — a small, hardcoded, industry-agnostic rule of
  thumb (`GENERIC_BENCHMARKS`), used only when neither of the above exists.
  Always reported with `confidence="low"` so nothing downstream mistakes a
  guess for a measurement.

`Baseline.reference_value` is the one place that encodes this precedence.
Three helper functions (`margin_baseline`, `supplier_delivery_baseline`,
`customer_value_baseline`) wrap `analytics.py`'s existing trend functions and
`BusinessContext.declared_baselines` — no computation is duplicated, only
reframed with a source and a confidence attached.

**A real bug caught during this step**: the first draft of these three
helpers used the *recent* trend value as `observed_value` (the reference to
compare against) instead of the *historical* one — i.e. it would have
compared "now" against "now" instead of "now" against "before". Caught by
`test_supplier_delivery_baseline_reflects_real_history` before it reached the
Snapshot layer. Worth naming explicitly: a baseline's own most basic property
(it comes from the past) is exactly the kind of thing that's easy to get
backwards.

## Significance (`app/core/significance.py`)

Deliberately **not** a single 0–100 score. Each dimension is a separate,
independently-inspectable field:

| Field | What it captures |
|---|---|
| `deviation` | `current_value - baseline.reference_value`, in the metric's own unit |
| `impact` | low/medium/high, from the *magnitude* of the deviation |
| `urgency` | low/medium/high, from impact + whether it's a one-off |
| `persistence` | new / ongoing / recurring, from a real Event Log recurrence count |
| `recurrence_count` | how many times this exact kind of signal has fired for this entity, counted from the Event Log |
| `correlation` | other open Risks/Opportunities on a linked entity (e.g. a product's own supplier) |
| `strategic_relevance` | low/medium/high, from whether the metric's domain/keyword appears in `BusinessContext.monitored_domains`/`stated_objectives` |
| `confidence` | inherited directly from the `Baseline` used |

`Significance.is_material` is one small, readable rule (high impact, OR high
urgency, OR recurring-and-not-low-impact) rather than a weighted formula —
kept auditable on purpose: anyone should be able to explain in one sentence
why something was or wasn't surfaced.

Significance does not detect anything on its own. It explains why something
Intelligence already flagged (an open Risk or Opportunity) does or doesn't
deserve attention right now.

**Known duplication, deliberately not unified yet**: the impact thresholds
used here (`_MARGIN_IMPACT_THRESHOLDS` etc. in `app/snapshot/service.py`)
mirror, but are not imported from, the severity thresholds already hardcoded
in `app.intelligence.risks.service`'s four detection rules. The two classify
different things (Significance classifies a *deviation from baseline*; the
existing rules classify an absolute recent value or a point_change) so they
aren't trivially the same function today. Unifying them into one shared
threshold table is the natural next refactor, deferred to avoid touching
twelve passing tests on stable detection code for a step whose job was to
introduce the new layer, not rewrite the old one.

## Business State Snapshot (`app/snapshot/service.py`)

A `BusinessStateSnapshot` is assembled **fresh, on every call**, from:

1. The company's `BusinessContext` (declared config + declared baselines).
2. Every currently OPEN Risk and Opportunity (from `HomeService`/direct
   query) — the Snapshot does not re-run monitoring itself; it annotates what
   Intelligence has already found with Baseline + Significance.
3. For each one, a `SnapshotArea` combining domain, the metric, its Baseline,
   its current value, and its Significance.

**This is explicitly not a second Data Core.** It owns no persisted state,
computes nothing that couldn't be recomputed from the Data Core and Event Log
at any time, and is cheap enough at this dataset's scale (~30 transactions,
5 areas) to rebuild on every request rather than cache. Caching is a listed
production bottleneck (see "What's deferred" below), not solved here.

`snapshot.material_areas` returns only the areas whose Significance says they
matter, sorted urgency-then-impact first — this is what the Orchestrator
actually consults, not the full unfiltered list.

## Wiring into the AI Orchestrator

Two questions the DoD asked to demonstrate, both real and tested:

- **Targeted question** ("What is our margin on the Sensor Module?") — routes
  exactly as before steps 12–13: keyword topic matching, entity resolution by
  name, targeted capabilities. Unchanged.
- **Broad/proactive question** ("What deserves my attention today?") — now
  calls `list_priorities` (summary counts, unchanged from step 12) **and**
  the new `get_business_state_snapshot` capability, then automatically
  drills into the single most significant area using the *same* targeted
  capability dispatch a named question would have used
  (`AIOrchestrator._dispatch_targeted_capabilities`, extracted from the
  targeted-question path specifically so both paths share one implementation
  and neither can call a capability its Agent doesn't declare).

Verified end-to-end against the real seeded dataset: asking "What deserves my
attention today?" automatically resolves the top-ranked area (a Supplier),
and calls `read_supplier` + `read_transactions` + `analyze_supplier_performance`
for it — the same three capabilities a human would have triggered by asking
about that supplier by name.

## Human feedback → configuration suggestions

`BusinessContextService.suggest_configuration_changes` looks at real
`ActionApproved`/`ActionRejected` events in the Event Log. If every recent
decision (a small streak threshold for this MVP's small dataset) went the
same way, it returns a `ConfigurationSuggestion` (field, current value,
suggested value, reason, evidence count) via `GET
/business-context/suggestions`.

**Nothing is ever applied automatically.** The suggestion is data returned to
whoever calls the endpoint; changing `BusinessContext` still requires an
explicit `PATCH /business-context` call. This is the whole "human feedback
enriches configuration, humans still decide" mechanism for this step — a
streak count, not a learning model.

## What's deferred (explicitly, not by omission)

- **Persistent baselines** — `BusinessContext` can hold a `declared_baseline`,
  but nothing yet writes a *computed* baseline back onto it for reuse across
  requests. Every Snapshot recomputes Baseline from scratch. Fine at this
  scale; a real deployment would want to cache/refresh this periodically.
- **Threshold unification** — see above.
- **Sector benchmarks** — `GENERIC_BENCHMARKS` is one hardcoded dict, not a
  per-industry table.
- **Recurrence/correlation are real but shallow** — recurrence counts an
  event type's occurrences via a Python-side scan of Event Log payloads
  (fine at dozens of rows, not built for scale); correlation checks exactly
  one relationship (a product's own supplier), not a general graph search.
- **The Snapshot doesn't proactively scan entities without an existing Risk/
  Opportunity** — it enriches what monitoring already found rather than
  re-deriving significance for every Supplier/Product/Customer on every call.
  A silent, "routine" entity with no open signal never appears in the
  Snapshot at all, by design (this is also how a future "why is nothing
  wrong with X" question would need a different mechanism than this one).
