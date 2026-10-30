from app.ai.agents.base import Agent

sales_agent = Agent(
    name="sales",
    description="Answers questions about customers and revenue trends.",
    capability_names=("read_customer", "read_transactions", "analyze_customer_value"),
)
