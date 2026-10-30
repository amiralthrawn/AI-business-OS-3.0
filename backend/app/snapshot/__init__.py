"""Business State Snapshot: a compact, deterministic, derived view of the
company's current state (Business Context + Baseline + Significance over
what Intelligence has already found), built so the AI Orchestrator can answer
a broad question by identifying important areas first and only then calling
targeted capabilities -- never by loading the whole Data Core into an LLM's
context. See brain/business_state.md."""
