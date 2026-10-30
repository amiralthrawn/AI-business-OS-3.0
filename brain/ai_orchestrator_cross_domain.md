# AI Orchestrator: Cross-Domain Reasoning Without a Named Entity

This document covers the enhancement built for the question locked in when
this step was opened: the Orchestrator already reasoned cross-domain since
step 12 (a "margin" question pulls in Finance + Procurement + Sales
capabilities in one pass), but only when the question named a specific
Supplier/Product/Customer to resolve. A genuinely broad question like *"Why
is our margin declining?"* — the brief's own example — named nothing, and
would have failed with "Could not identify which supplier, product or
customer this question refers to." This step closes that gap without adding
a new agent, a new capability, or a new detection/reasoning system.

## What already existed (step 12), unchanged

```text
Named-entity question ("What is our margin on the Sensor Module?")
      ↓
_match_agents_for_topics -- keyword routing, possibly several agents
      ↓
_resolve_supplier / _resolve_product / _resolve_customer -- substring match
      ↓
_dispatch_targeted_capabilities -- union of matched agents' capabilities
      ↓
one LLM call -- synthesizes one answer from the merged structured context
```

This path, `_handle_analytical_request`, is completely untouched. So is the
broad "what deserves my attention?" path (`_handle_priorities_request`),
which already consulted the Business State Snapshot before this step and
still does, unchanged (Definition-of-Done test #6 in
`tests/test_ai_orchestrator_cross_domain.py` proves this explicitly).

## What was added: `_handle_cross_domain_request`

When `_handle_analytical_request` matches one or more agents by topic
keyword but resolves **no** Supplier/Product/Customer at all, it now calls
`_handle_cross_domain_request` instead of raising immediately:

```text
Cross-domain question, no named entity ("Why is our margin declining?")
      ↓
_match_agents_for_topics -- same keyword routing as before (margin -> finance+procurement+sales)
      ↓
get_business_state_snapshot -- the SAME Snapshot capability the priorities path already used
      ↓
filter material_areas to the matched domain(s)
      ↓
no area found -> OrchestratorError ("insufficient context", never a guess)
      ↓
for each significant area: _resolve_entity_by_ref + _dispatch_targeted_capabilities
      (both reused verbatim -- the exact same functions a named question uses)
      ↓
one LLM call -- synthesizes ONE answer from every area's merged context
```

This reuses, rather than reimplements, every piece: the Snapshot (already
built in steps 14–17), `_resolve_entity_by_ref` and
`_dispatch_targeted_capabilities` (already built in step 12/14). The only
new code is the glue that decides *which* entities to drill into when the
question itself doesn't say.

## Never scans the whole Data Core

The Orchestrator only ever looks at entities the Snapshot's own
`material_areas` already flagged as significant — it does not iterate every
Supplier/Product/Customer in the company. Verified by
`test_cross_domain_question_only_touches_the_significant_entity_not_every_supplier`:
five unrelated, non-anomalous suppliers/products are seeded alongside the
one real Risk, and the resulting context contains exactly one area beyond
the Snapshot summary itself — none of the five "noise" suppliers' names
appear anywhere in the response.

## Insufficient context is a clean error, never a guess

When no `material_area` falls within the matched domain(s), the Orchestrator
raises `OrchestratorError` with an explicit message naming the domain(s) it
checked, rather than answering with nothing or inventing a plausible-sounding
cause. This is the same "clean, expected failure" pattern already used
throughout `app.ai.orchestrator` (unroutable questions, unresolvable named
entities) — extended to the new path rather than given its own error type.

## Avoiding a real cache collision: one dict per area, not a shared one

`_call`'s cache is keyed by capability name alone (`if name in
capabilities_used: return context[name]`), which was always correct before
this step because every existing path resolves **at most one** entity per
request. `_handle_cross_domain_request` can genuinely need the *same*
capability (e.g. `analyze_margin`) for *different* entities across several
significant areas in the same request — reusing the shared cache as-is would
have silently returned the first entity's cached result for every
subsequent area needing the same capability.

Rather than changing `_call`'s signature or cache key (which every other,
already-tested call site depends on), each area gets its own scratch
`area_context`/`area_capabilities` passed into `_dispatch_targeted_capabilities`,
and is merged into the outer context afterward under a namespaced key
(`"{domain}: {title}"`). This keeps `_call` and `_dispatch_targeted_capabilities`
completely unchanged — verified by
`test_cross_domain_question_aggregates_two_distinct_domains_and_entities`,
which seeds two real, unrelated Risks (a finance-domain margin issue and a
procurement-domain delivery issue) and confirms both entities' capability
results appear intact, under separate keys, in the same response.

## What was verified end-to-end (not just unit tests)

Ran against the real seeded dataset (`data/seed.py`, already producing 4
Risks + 1 Opportunity across finance/procurement/sales via steps 12–17):

```text
POST /ai/ask {"question": "Why is our margin declining?"}

agent: "finance, procurement, sales"
capabilities_used: [
  "get_business_state_snapshot", "read_supplier", "read_transactions",
  "analyze_supplier_performance", "analyze_margin", "read_customer",
  "analyze_customer_value"
]
context keys:
  - get_business_state_snapshot
  - procurement: Supplier cost increase of 25% on product Sensor Module
  - finance: Margin deterioration on product Steel Frame Assembly
  - procurement: Supplier performance deterioration: Iberia Logistics Parts
  - sales: Customer decline: BrightWorks Ltd
  - sales: Growing customer: Metroline Corp
  - procurement: Insight: Coastal Metal Supply -- delivery_delay_days anomaly worth watching
requires_human_validation: false
```

One question, no named entity, six significant areas across all three
domains, seven distinct capabilities called, and a single response
synthesized from all of it — the concrete demonstration the brief's own
"Pourquoi notre marge baisse ?" example asked for.

## What's deferred (explicitly, not by omission)

- **No ranking/capping of how many areas get drilled into.** Every material
  area in the matched domain(s) gets a full capability dispatch; on this
  MVP's small dataset that's at most a handful, but a much larger company
  would want a cap (e.g. top N by urgency, reusing `material_areas`'s
  existing urgency/impact sort) before this scales further. Not built here,
  per "garde l'implémentation simple."
- **No cross-area deduplication beyond the cache-collision fix above.** If
  two areas resolve to the exact same entity (shouldn't currently happen,
  since Snapshot areas are already deduplicated per entity), they would be
  dispatched twice under two different area keys. Not a real risk today,
  not specifically guarded against.
- **Still no planning, no multi-step tool-calling loop, no autonomous
  agent.** One routing pass, one Snapshot lookup, one round of capability
  calls per relevant area, one LLM call — exactly the same bounded shape the
  Orchestrator has had since step 12, just applied to more than one area
  when the question warrants it.
