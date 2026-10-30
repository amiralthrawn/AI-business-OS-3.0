# Business Context — concept and roadmap

## The problem this solves

Through step 12, every Intelligence rule used a hardcoded, universal threshold
(margin deterioration ≥5 points, cost increase ≥10%, and so on) — the same
rule for every company, regardless of its industry, its stated priorities, or
what "normal" actually looks like for it. That does not scale to "an OS that
understands *this* business": a 10% cost swing might be routine for a
commodity trader and alarming for a fixed-price manufacturer.

**Business Context** is the layer that is supposed to close that gap: the
company-specific configuration and accumulated understanding that lets
Monitoring, Intelligence and AI reason about this particular company instead
of a generic one.

## What it is built from (the full vision)

* **Initial configuration** — declared during onboarding, "like setting up a
  new iPhone": what to watch, what counts as important, notification
  frequency/level, what Home should foreground, stated objectives.
* **Sector of activity** — industry-specific norms (not built yet; see
  "Deliberately not built" below).
* **Leadership priorities and preferences** — explicit, human-declared goals.
* **Real data and history** — the Data Core and Event Log already accumulate
  this; Business Context is meant to *summarize* it, not duplicate it.
* **Baselines computed from that history** — "what's normal for this
  company", derived over time rather than assumed.
* **Human decisions and interactions over time** — every approve/reject on a
  proposed action (steps 10–11) is a signal about what this company actually
  considers worth acting on.

## Conceptual architecture

```text
DATA CORE
   ↓
HISTORICAL CONTEXT  +  BUSINESS CONFIGURATION
   ↓
BUSINESS CONTEXT
   ↓
SIGNIFICANCE / MONITORING
   ↓
AI INTELLIGENCE
   ↓
RISK / OPPORTUNITY / INFORMATION / DECISION
   ↓
HOME
   ↓
ACTIONS
```

Business Context sits between the Data Core and Monitoring/Intelligence: it is
what those layers should eventually consult before deciding whether something
is worth surfacing, instead of applying the same rule to every company.

## What actually got built

A static, human-editable configuration entity plus a real (if simple) human
feedback mechanism — deliberately not an adaptive learning system:

* **Entity**: `app.core.entities.BusinessContext` — one row per Company
  (`company_id` unique). Onboarding-style declared fields: `company_size`,
  `country`, `business_model` (sector itself stays on `Company.industry`,
  not duplicated), `monitored_domains`, `home_focus`, `notification_level`,
  `stated_objectives`. Every one of these is nullable/empty by default —
  "not answered" is a real, distinct state, never silently guessed at.
  `declared_baselines` (JSON `{metric: value}`) holds company-declared
  targets, kept structurally and semantically separate from anything
  *observed* (see `brain/business_state.md` — this is the field
  `app.core.baseline` reads to distinguish "declared" from "observed"
  baselines). `learned_notes` is an append-only list of short factual
  observations the system writes for itself; nothing rewrites past entries.
* **Service**: `app.business_context.service.BusinessContextService` —
  `get_or_create`, `update` (touches only the fields explicitly passed),
  `add_learned_note`, and `suggest_configuration_changes` (see below).
* **API**: `GET`/`PATCH /business-context`, `GET /business-context/suggestions`.
* **Seed**: `data/seed.py` populates a full, plausible default context
  (size, country, business model, a declared `margin_pct` target of 30% that
  the real transaction history deliberately falls short of — demonstrating
  "declared ≠ observed" with real data, not just in a unit test).

**Human feedback → suggestions, still deferred → automatic change**:
`suggest_configuration_changes` reads real `ActionApproved`/`ActionRejected`
counts from the Event Log and proposes a `notification_level` change when
every recent decision went the same way. It returns a suggestion; it never
calls `update()` itself. A human still has to act on it via a separate
`PATCH`. This is genuinely wired and tested, not a stub — see
`tests/test_business_context_suggestions.py`.

**Still not wired into detection behavior**: no Intelligence rule reads
`notification_level` or `monitored_domains` to change its own threshold or
filter which domains it watches yet — see `brain/business_state.md` for why
(the Significance layer built alongside this introduces the machinery that
would make this wiring meaningful, and unifying it with the existing
hardcoded rule thresholds is a named, deferred refactor, not an oversight).

## Deliberately not built (and why)

* **Adaptive learning** — the OS proposing configuration changes beyond the
  one simple streak-based suggestion above requires more decision history
  than exists in this MVP's dataset. Building a general learning mechanism
  before there's enough to learn from would be speculative.
* **Sector profiles** — pre-built configuration templates per industry. A
  content problem more than an architecture one; the current shape doesn't
  need to change to add it later.
* **Threshold wiring** — see `brain/business_state.md`'s "known duplication"
  note; Significance exists now, but the four hardcoded Intelligence rules
  from steps 6–12 haven't been refactored to read from it.
* **Persisted computed baselines** — `declared_baselines` is human-declared
  and persisted; *observed* baselines are still recomputed fresh on every
  request rather than cached on `BusinessContext`. See `brain/business_state.md`.
