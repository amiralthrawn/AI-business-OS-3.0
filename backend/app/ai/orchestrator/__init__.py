"""Routes a user question to relevant capabilities/agents, executes them, and
synthesizes a response. Deterministic and bounded: one routing pass, one round
of capability calls, one LLM call -- no autonomous tool-calling loop."""

from app.ai.orchestrator.service import AIOrchestrator, AskAIResult, OrchestratorError

__all__ = ["AIOrchestrator", "AskAIResult", "OrchestratorError"]
