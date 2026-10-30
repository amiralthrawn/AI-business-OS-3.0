"""MVP risk detection rule for SupplierCostIncreased.

The Data Core doesn't yet aggregate enough purchase history to compute a real
supplier concentration/dependency signal, so the rule is intentionally the
simplest one that uses data actually available today: any cost increase of
10% or more is treated as worth a Risk. This exists to prove the event
pipeline end-to-end, not to be the final risk-scoring engine -- concentration
should be added once the Data Core can aggregate spend per supplier.
"""

from app.core.entities.risk import RiskSeverity

COST_INCREASE_RISK_THRESHOLD_PCT = 0.10
HIGH_SEVERITY_THRESHOLD_PCT = 0.25


def is_significant_cost_increase(variation_pct: float) -> bool:
    return variation_pct >= COST_INCREASE_RISK_THRESHOLD_PCT


def severity_for_cost_increase(variation_pct: float) -> RiskSeverity:
    if variation_pct >= HIGH_SEVERITY_THRESHOLD_PCT:
        return RiskSeverity.HIGH
    return RiskSeverity.MEDIUM
