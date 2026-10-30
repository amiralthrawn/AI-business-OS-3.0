"""End-to-end proof of the DoD chain for this step:

Data / History / Configuration
        -> Business Context
        -> Baseline
        -> Significance
        -> Business State Snapshot
        -> AI Orchestrator
        -> targeted capabilities

A broad, proactive question ("what deserves my attention?") over the full
demo dataset must not stop at a summary: it should identify the most
significant area via the Snapshot and automatically fetch targeted detail for
it, exactly as a named question would have.
"""

from app.ai.capabilities import build_capability_registry
from app.ai.llm import DeterministicLLMClient
from app.ai.orchestrator import AIOrchestrator
from app.event_bus import build_event_bus
from data.seed import seed


def test_priorities_question_drills_into_the_most_significant_area(db_session, session_factory):
    bus = build_event_bus(session_factory)
    seed(db_session, bus)

    orchestrator = AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), bus)

    result = orchestrator.ask("What deserves my attention today?")

    assert result.agent == "priorities"
    assert "list_priorities" in result.capabilities_used
    assert "get_business_state_snapshot" in result.capabilities_used

    snapshot_context = result.context["get_business_state_snapshot"]
    assert len(snapshot_context["material_areas"]) > 0

    # The drill-down actually happened: at least one targeted capability
    # beyond the two summary ones was called, using real data from the Data
    # Core (not fabricated), for whichever area the Snapshot ranked first.
    targeted_capabilities = set(result.capabilities_used) - {"list_priorities", "get_business_state_snapshot"}
    assert len(targeted_capabilities) > 0
    assert targeted_capabilities <= {
        "read_supplier", "read_product", "read_customer", "read_transactions",
        "analyze_margin", "analyze_supplier_performance", "analyze_customer_value",
    }


def test_priorities_question_on_an_empty_business_never_fails(db_session, event_bus):
    """No company, no data at all -- the broad question must still resolve
    cleanly instead of erroring out because there is nothing to snapshot."""

    orchestrator = AIOrchestrator(db_session, build_capability_registry(), DeterministicLLMClient(), event_bus)

    result = orchestrator.ask("What deserves my attention today?")

    assert result.agent == "priorities"
    assert result.context["get_business_state_snapshot"]["material_areas"] == []
