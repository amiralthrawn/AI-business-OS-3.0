from app.ai.agents.base import Agent

finance_agent = Agent(
    name="finance",
    description="Analyzes transactions and margins across the business.",
    capability_names=("read_transactions", "analyze_margin"),
)
