from app.ai.agents.base import Agent

priorities_agent = Agent(
    name="priorities",
    description="Answers 'what deserves my attention?' by listing open Risks and Opportunities ranked by "
    "impact, and can consult the Business State Snapshot to identify which areas are significant enough "
    "to drill into with targeted capabilities.",
    capability_names=("list_priorities", "get_business_state_snapshot"),
)
