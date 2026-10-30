# Business Event Interpretation Layer

This document covers the layer built directly above the Business Observation
Engine (`brain/observation_engine.md`) to answer the question locked in when
this step was opened: **"what does this Business Event mean for this
company?"**

## The three concepts, kept explicitly separate

```text
Business Event  = fait détecté                (app.observation, unchanged)
Interpretation  = compréhension produite par l'IA   (app.interpretation, this layer)
Risk/Opportunity = résultat métier dérivé      (app.intelligence's own Risk/
                    Opportunity rows, from the older per-metric rules --
                    NOT created or replaced by this layer)
```

An Interpretation's `type` field (`risk` / `opportunity` / `insight` /
`observation`) is the AI's own classification of what a Business Event means
— a judgment call, not a new Data Core row. The actual `Risk`/`Opportunity`
tables from steps 6–12 are untouched: this layer coexists with them rather
than replacing them (see "Progressive, backward-compatible integration"
below for exactly how the two are reconciled in the Snapshot).

## The chain

```text
Observation Engine (app.observation)
      ↓
Business Event (ObservationDetected)
      ↓
Context Assembly (app.interpretation.context)
      ├── Business Context        (declared config, declared_baselines)
      ├── Baseline + Significance (already embedded in the Observation's
      │                            own payload -- never recomputed)
      ├── Business State Snapshot (a compact summary, not the whole thing)
      ├── Related/correlated Observations
      └── Targeted AI capabilities (only the ones the event's domain agent
                                     already declares -- reused, not new)
      ↓
LLM (app.ai.llm.LLMClient -- unchanged abstraction)
      ↓
Interpretation (app.interpretation.engine.Interpretation)
      ├── type: risk | opportunity | insight | observation
      ├── title, explanation, potential_impact, recommendation, confidence
      ├── observations_used, capabilities_consulted
      ↓
Action Proposal (only for risk/opportunity, only if not already covered)
      ↓
Human Validation (the EXISTING ActionsService/ActionExecutor -- unchanged)
```

## Classification is deterministic, not LLM-decided

`app.interpretation.engine.classify()` is a small, generic, auditable
function of Significance fields the Observation Engine already computed —
never a second detection pass, never a per-event-type `if` branch, and
**never a call to the LLM**. This was a deliberate design choice, for two
reasons:

1. **Consistency with the rest of the system.** Every classification in this
   codebase so far (`Significance.is_material`, `_classify_impact`,
   `_classify_urgency`, ...) is a small, readable, auditable rule rather than
   a black box — the brief's own "Business Event reste factuel et
   déterministe" instruction reads naturally as extending that same
   philosophy to the risk/opportunity/insight call itself, not just to the
   underlying numbers.
2. **Testability without a live LLM.** `app.ai.llm.DeterministicLLMClient`
   (used throughout this project's test suite and by default when no OpenAI
   key is configured) is a plain echo of its prompt — it cannot reliably
   return a parseable classification. Making the type/confidence a
   deterministic function of already-computed Significance fields keeps the
   three required MVP demonstrations (Risk / Opportunity / Insight)
   reproducible in CI with no network access, exactly like every other
   detection rule in this codebase.

The LLM's role is confined to `explanation` — the free-text business
reasoning for *why* the data supports the classification — never the
classification itself, and it never touches the Data Core, a Baseline, an
Observation or a Significance.

The rule, in `_METRIC_DIRECTION` (a one-line-per-metric polarity table,
registered once per known Observable — the same pattern `impact_thresholds`
already uses in `app.observation.registry`, not a new per-event rule) plus
`Baseline.confidence`:

| Baseline confidence | Result |
|---|---|
| `insufficient` (no real baseline to compare against at all) | `observation` — a plain fact, no judgment forced |
| `low` (a generic-benchmark or thin-sample baseline) | `insight` — the magnitude may be real, but the reference it's measured against is a guess |
| `medium`/`high`, deviation unfavorable for this metric | `risk` |
| `medium`/`high`, deviation favorable for this metric | `opportunity` |

This directly implements "Ne force jamais un événement à devenir
Risk/Opportunity si les données ne le permettent pas": a large deviation
measured against a low-confidence baseline stays an `insight`, never gets
inflated into a confident-sounding Risk.

## Context Assembly (`app/interpretation/context.py`)

Builds a compact dict — never the whole Data Core — from:

- the Business Event's own fields (observable, domain, entity, current value);
- Baseline + Significance, read directly from the Observation's own payload
  (no recomputation, same pattern `app.snapshot`'s `_build_area_for_observation`
  already established);
- the company's Business Context (monitored domains, stated objectives, the
  declared baseline for this specific metric, if any);
- a Business State Snapshot *summary* (open Risks/Opportunities counts,
  material area count) — not the full Snapshot object;
- any correlated Observations from the same cross-domain cluster
  (app.observation's own Product↔Supplier correlation, passed through);
- and, only for a domain some Agent already covers, the same targeted AI
  capabilities a human's Ask AI question about that entity would trigger —
  reusing `AIOrchestrator._dispatch_targeted_capabilities` and
  `_resolve_entity_by_ref` directly rather than reimplementing entity
  resolution or capability dispatch.

## Action Proposal → Human Validation (no new mechanism)

When an Interpretation classifies as `risk` or `opportunity` (never
`insight`/`observation` — consistent with "ne force jamais"), the engine
calls `ActionsService.propose_task` — the exact same Human-in-the-Loop
mechanism the `create_task` AI capability already uses. The resulting Task is
`PENDING_VALIDATION` and carries `pending_action="create_task"`, so it is
approved/rejected and executed through the existing, unmodified
`POST /actions/tasks/{id}/approve` endpoint and `ActionExecutor` — this layer
adds no new execution path and never runs anything itself.

**Deduplication against the older per-metric flows**: before proposing,
`_already_covered_by_existing_flow` checks whether an open Risk/Opportunity
already exists for the same entity. If one does, the Interpretation is still
produced (it's additive/informational — the narrative and classification are
valuable even when a Risk already exists), but the Action Proposal is
skipped, so this layer never creates a second, duplicate Task for a
phenomenon the older flow already surfaced. Verified by
`test_no_duplicate_action_when_entity_already_has_an_open_risk`.

## Progressive, backward-compatible Snapshot integration

`build_snapshot()` (`app/snapshot/service.py`) now layers three kinds of
areas, in order of precedence:

1. **`risk`/`opportunity`** — from the older per-metric rules, unchanged,
   always wins for a given entity.
2. **`interpretation`** — from this layer's `EventInterpreted` events, shown
   for an entity that has neither of the above. Richer than a plain
   observation: carries `interpretation_type`, `explanation` and
   `recommendation` (three new, optional `SnapshotArea` fields, defaulting to
   `None` for every other kind — additive, not a breaking change).
3. **`observation`** — from `app.observation`'s raw `ObservationDetected`
   events, shown only for an entity covered by neither of the above (e.g. an
   Observable whose ObservationDetected event hasn't been interpreted yet).

This is the concrete mechanism for "l'intégration doit être progressive et
rétrocompatible": nothing about the existing Risk/Opportunity flow changed,
and a raw Observation is only ever *upgraded* to a richer representation, in
place, never duplicated alongside it.

## What was verified end-to-end (not just unit tests)

Ran against a freshly rebuilt seeded database (`data/seed.py`, now also
calling `run_interpretation_sweep` after `run_observation_sweep`):

```text
5 observation events published, 5 interpreted ({'risk': 3, 'opportunity': 1,
'insight': 1, 'observation': 0}), 0 actions proposed.
```

- **Risk** (`un événement fournisseur/coût → Risk`): Steel Frame Assembly's
  margin fell to 13.6%, well under the company's declared 30% target
  (`baseline_source="declared"`, `confidence="high"`) — driven by Northline
  Steel's cost creep (Chain 1). Classified `risk`, with a recommendation.
- **Opportunity** (`un événement commercial positif → Opportunity`):
  Metroline Corp's revenue roughly tripled against the company's declared
  "±5% is normal" target — classified `opportunity`, with a recommendation.
- **Insight** (`un événement intéressant mais non clairement Risk/Opportunity
  → Insight`): a new seed supplier, **Coastal Metal Supply** (Chain 4, added
  for this step — only 3 shipments on record, all 6–7 days late). The
  deviation is large, but with only 3 data points and no declared target,
  the baseline falls back to a generic benchmark at `confidence="low"` —
  classified `insight`, deliberately with **no** recommendation.
- **Idempotence against a real database**: re-running `POST
  /interpretation/sweep` immediately after produced
  `{"observations_interpreted": 0, "actions_proposed": 0, ...}`.
- **`POST /ai/ask`** with "What deserves my attention today?" surfaces the
  Coastal `interpretation`-kind area alongside the four `risk` areas and one
  `opportunity` area in `material_areas`, confirming the Snapshot integration
  through the real Orchestrator path, not just a direct `build_snapshot()` call.
- **`actions_proposed: 0` in the full demo run is expected, not a bug**: all
  four of the pre-existing anomalies (margin, delivery, two customer trends)
  already have an open Risk/Opportunity from the older per-metric rules, so
  the dedup guard correctly skips proposing a duplicate Task for any of them;
  the one genuinely new entity (Coastal) classifies as `insight`, which never
  proposes an action by design. The Action Proposal → Human Validation
  mechanics themselves are proven by dedicated unit tests
  (`test_run_interpretation_sweep_interprets_and_proposes_a_pending_task_only`,
  `test_proposed_task_can_be_approved_through_the_existing_action_executor`)
  against an isolated scenario with no pre-existing Risk — the same
  "proven by unit test, not by the demo run" honesty already established for
  `app.observation`'s own cross-domain correlation.

## What's deferred (explicitly, not by omission)

- **The LLM's explanation is only as good as the configured client.** With no
  OpenAI key, `DeterministicLLMClient` echoes the prompt back rather than
  writing real prose — the classification, confidence, recommendation and all
  structured fields are still fully correct and real either way (they don't
  depend on the LLM), but the free-text `explanation` only reads naturally
  once a real LLM is configured.
- **No Insight → Risk/Opportunity promotion over time.** An `insight`
  classification doesn't get automatically re-evaluated as more history
  accumulates for that entity; a later sweep would produce a fresh
  Interpretation with its own (possibly different) classification once the
  entity's Baseline confidence improves, but nothing here upgrades or amends
  a past Interpretation in place.
- **One Interpretation per Observation, not per correlated cluster.** When
  `app.observation` correlates two anomalies (e.g. a Product's margin issue
  with its own Supplier's delivery issue), only the *primary* Observation
  gets its own `ObservationDetected` event (by that layer's own design), so
  only it gets interpreted; the correlated Observation's data is still
  visible to the LLM via `correlated_observations` in the context, but it
  does not get its own separate Interpretation.
- **No frontend UI for Interpretation's narrative yet.** The `explanation`/
  `recommendation` fields reach the Snapshot (and therefore whatever consumes
  it, like the priorities/broad-question Ask AI path) but no new Home/
  Intelligence page renders them directly — deferred, matching how
  `app.observation`'s own step didn't add new frontend UI either.
