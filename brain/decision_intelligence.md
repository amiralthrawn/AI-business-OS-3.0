# Decision Intelligence Layer

This document covers the layer built directly above the Business Event
Interpretation Layer (`brain/interpretation_engine.md`) to answer the
question locked in when this step was opened: **"quelles décisions sont
envisageables ?"** — moving the OS from "I detect and understand" to "I can
help decide," without ever deciding on the business's behalf.

## The chain, extended

```text
Business Event (app.observation)
      ↓
Interpretation (app.interpretation) -- "what's happening and why it matters"
      ↓
Decision Intelligence (app.decision) -- "what could we do about it, and what
      ↓                                  do we recommend, if anything"
Recommendation
      ↓
Action Proposal (only when confident, only if not already covered)
      ↓
Human Validation (the EXISTING ActionsService/ActionExecutor -- unchanged)
```

`Decision` is a new, richer structure sitting between Interpretation and
Action Proposal:

```text
problem            <- the Interpretation's own title, not re-derived
options[]           label, expected_benefit, trade_offs
potential_impact    <- the Interpretation's own field, reused
confidence          <- the Interpretation's own field, reused
data_used           <- the Interpretation's own observations_used, reused
capabilities_consulted
recommendation      chosen_option (str | None), reasoning (str)
```

A Decision can exist without an Action, and a Recommendation can exist
without an Action being proposed — both explicit requirements from the
brief, and both true by construction: `_maybe_propose_action` only runs when
`recommendation.chosen_option is not None`, which itself is only set for a
confident `risk`/`opportunity` classification.

## Responsibility moved: Interpretation no longer proposes a Task

The previous step's `app.interpretation.engine` proposed a Task itself for
any confident risk/opportunity Interpretation. This step's own target
diagram places Action Proposal *after* Decision Intelligence, not directly
after Interpretation, so that responsibility (the `_maybe_propose_action`
function, the `_already_covered_by_existing_flow` dedup guard, and the
`ActionsService` import) moved from `app.interpretation.engine` to
`app.decision.engine`. `run_interpretation_sweep` now only publishes
`EventInterpreted` and returns `{"observations_interpreted", "by_type"}` (no
more `actions_proposed` key). This is documented as decision #16 in
`brain/decisions.md` — a deliberate, minimal adjustment to an
already-shipped module in response to the new target architecture, not a
rewrite of Interpretation's own classification or explanation logic (both
untouched).

## Options are a small, generic, per-domain lookup -- not a new agent

`app.decision.engine._RISK_OPTIONS` / `_OPPORTUNITY_OPTIONS` hold exactly
three options per (decision type, domain) — finance, procurement, sales, the
same three domains this project has had since step 12. Each domain's three
options follow one shape: two proactive options, one passive
("absorb"/"monitor"/"reassess") option. This is metadata, the same pattern
`app.interpretation.engine`'s own (now-removed) `_recommendation()` template
already used — not a new agent, not a rule tied to a specific metric or
event instance, and trivially extensible (a fourth domain is one more
dict entry, never a new class or a change to `build_decision`).

**Recommendation is deterministic, not LLM-decided** — for the same reason
`app.interpretation.engine.classify()` is deterministic (see
`brain/interpretation_engine.md`): `DeterministicLLMClient` cannot reliably
choose among options, so `_build_recommendation` always combines the two
proactive options (`f"{options[0].label} + {options[1].label}"`), mirroring
the brief's own example exactly ("Investigate renegotiation + alternative
supplier" — skipping "absorb the cost temporarily"). The LLM's role is
confined to `reasoning`: given the context and the chosen combination, it
explains *why*, in one or two sentences, never proposing a different
combination and never touching the Data Core.

## Context Assembly is reused, not reimplemented

`build_decision` calls `app.interpretation.context.assemble_context` again,
against the same underlying `ObservationDetected` entry the Interpretation
itself used — the identical Business Event + Significance + Business Context
+ Baseline + Snapshot summary + targeted capabilities — then folds the
Interpretation's own output (`type`, `title`, `explanation`, `confidence`)
into that context under an `"interpretation"` key before handing it to the
LLM. No second, parallel context-assembly function was written; no capability
call happens beyond what `assemble_context` already dispatches for the
event's domain.

## Insufficient context: a Decision that honestly recommends nothing

When the underlying Interpretation is `insight` or `observation` (not
confident enough per `app.interpretation.engine.classify`), `_build_options`
returns `[]` and `_build_recommendation` skips the options-based prompt
entirely, asking the LLM only to explain *why* there isn't enough reliable
information to recommend a specific action. The resulting Decision still has
a `type`, a `problem`, `data_used` and a `reasoning` — the AI still says
something — but `options == []` and `recommendation.chosen_option is None`,
and `_maybe_propose_action` never runs for it. This is the concrete
implementation of "Ne force jamais un événement à devenir Risk/Opportunity"
one layer further: even for a risk/opportunity-adjacent signal, if the
underlying Interpretation itself wasn't confident, Decision Intelligence
does not manufacture a confident-sounding recommendation on top of it.

## Progressive, backward-compatible Snapshot integration

`build_snapshot()` now layers four kinds of areas, in order of precedence:

1. **`risk`/`opportunity`** (unchanged, from the older per-metric rules) —
   always wins for a given entity.
2. **`decision`** (new, from `app.decision`'s `DecisionProposed` events) —
   shown for an entity that has neither of the above. The richest
   representation: carries `interpretation_type` (the Decision's own `type`),
   `explanation` (the recommendation's `reasoning`), `recommendation` (the
   `chosen_option`, possibly `None`) and the new `decision_options` field
   (the full options list, each `{label, expected_benefit, trade_offs}`).
3. **`interpretation`** (unchanged) — shown only when no Decision exists yet
   for that Interpretation (e.g. the decision sweep hasn't run).
4. **`observation`** (unchanged) — shown only when neither of the above
   exists for that Observation.

Nothing about the existing Risk/Opportunity flow, or the Interpretation
layer's own Snapshot area, was replaced — a raw signal is only ever
*upgraded* to a richer representation, in place, never duplicated alongside
it, exactly the same mechanism `app.interpretation.md` established for its
own layer.

## What was verified end-to-end (not just unit tests)

Ran against a freshly rebuilt seeded database (`data/seed.py`, now also
calling `run_decision_sweep` after `run_interpretation_sweep`):

```text
5 interpreted ({'risk': 3, 'opportunity': 1, 'insight': 1, 'observation': 0}),
5 decisions made ({'risk': 3, 'opportunity': 1, 'insight': 1, 'observation': 0}),
0 actions proposed.
```

- **Risk** (Steel Frame Assembly, margin): 3 options generated from the
  `finance` catalog, recommendation `"Review pricing or cost structure for
  the affected product + Investigate the underlying cost or revenue driver
  directly"`.
- **Opportunity** (Metroline Corp, growth): 3 options from the `sales`
  catalog, recommendation `"Engage Metroline Corp to expand the relationship
  (upsell/cross-sell) + Propose a longer-term or higher-volume contract to
  lock in the growth"`.
- **Insufficient context** (Coastal Metal Supply, insight): `0` options,
  `chosen_option: null`, confirmed via direct inspection of the `events`
  table.
- **No automatic execution, verified twice**: direct inspection of the
  `tasks` table on the fresh database shows only the 4 `PENDING_VALIDATION`
  Tasks the *older* per-metric `RiskCreated` handler already produced (from
  steps before this one) — Decision Intelligence proposed zero new Tasks on
  this dataset, correctly, because every one of its 4 non-insight Decisions
  is for an entity the older flow already covers (the dedup guard). The
  Action Proposal → Human Validation mechanics themselves are proven by
  dedicated unit tests against an isolated, uncovered scenario
  (`test_run_decision_sweep_proposes_a_pending_task_only_for_a_risk`,
  `test_proposed_task_can_be_approved_through_the_existing_action_executor`)
  — the same "proven by unit test, not by the demo run" honesty already
  established for `app.observation`'s correlation and `app.interpretation`'s
  own action-proposal dedup in the prior step.
- **Idempotence against a real database**: re-running `POST /decision/sweep`
  immediately after produced `{"decisions_made": 0, "actions_proposed": 0, ...}`.
- **`POST /ai/ask`** with "What deserves my attention today?" surfaces the
  Coastal `decision`-kind area (with `recommendation: null`, correctly, since
  it's an insight) in `material_areas`, confirming the Snapshot integration
  through the real Orchestrator path.

## What's deferred (explicitly, not by omission)

- **No quantitative decision engine yet.** No Monte Carlo, no mathematical
  optimization, no financial simulation, no forecasting. The architecture
  (`build_decision` computing options + a recommendation from a context dict)
  can later grow a second, quantitative option-generation strategy (e.g. a
  scenario-modeling engine) without touching Interpretation, Snapshot or the
  Orchestrator — but none is built here, per the brief's explicit exclusion.
- **No option catalog beyond finance/procurement/sales.** A domain outside
  this MVP's three falls back to the `finance` entry (the most generic of
  the three) rather than failing — a deliberate, honest default, not a
  silent gap.
- **One Decision per Interpretation**, same 1:1 relationship
  Interpretation has with its source Observation — no batching of related
  Decisions across entities (e.g. one combined Decision for "the whole
  Northline relationship") in this MVP.
- **No frontend UI for Decision's options/trade-offs yet.** The
  `decision_options` field reaches the Snapshot (and therefore Ask AI's
  broad-question path) but no new Home/Intelligence page renders it directly
  — deferred, matching how neither prior layer added new frontend UI either.
