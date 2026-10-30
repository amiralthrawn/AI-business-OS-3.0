"""Decision Intelligence: the layer that turns an Interpretation into
concrete, human-reviewable options -- "what could we do about this?" -- and a
reasoned recommendation, never deciding or executing on the business's
behalf. Sits directly above app.interpretation and reuses its context
assembly, the existing AI Orchestrator's capabilities and LLM abstraction,
and the existing Human-in-the-Loop mechanism for any resulting Task
proposal. See brain/decision_intelligence.md.
"""
