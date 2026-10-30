from app.ai.agents.base import Agent

procurement_agent = Agent(
    name="procurement",
    description="Answers questions about suppliers, products and purchasing activity, and can propose "
    "(never execute) a Task to review a supplier or product.",
    capability_names=(
        "read_supplier",
        "read_product",
        "read_transactions",
        "analyze_supplier_performance",
        "create_task",
    ),
)
