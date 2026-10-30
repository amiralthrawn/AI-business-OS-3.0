from app.core.baseline import build_baseline
from app.core.significance import assess_significance


def test_high_impact_deviation_is_material():
    baseline = build_baseline("margin_pct", observed_value=0.25, sample_size=8)

    significance = assess_significance(
        baseline, current_value=0.10, impact_thresholds=(0.05, 0.10)
    )

    assert significance.impact == "high"
    assert significance.urgency == "high"
    assert significance.is_material is True
    assert significance.deviation == 0.10 - 0.25


def test_low_impact_new_signal_is_not_material():
    baseline = build_baseline("margin_pct", observed_value=0.25, sample_size=8)

    significance = assess_significance(
        baseline, current_value=0.24, impact_thresholds=(0.05, 0.10)
    )

    assert significance.impact == "low"
    assert significance.persistence == "new"
    assert significance.is_material is False


def test_recurring_medium_impact_becomes_material_via_urgency():
    baseline = build_baseline("margin_pct", observed_value=0.25, sample_size=8)

    significance = assess_significance(
        baseline,
        current_value=0.18,  # 0.07 deviation -> medium impact (between 0.05 and 0.10)
        impact_thresholds=(0.05, 0.10),
        recurrence_count=2,
    )

    assert significance.impact == "medium"
    assert significance.persistence == "recurring"
    assert significance.urgency == "high"
    assert significance.is_material is True


def test_significance_never_collapses_into_a_single_score():
    baseline = build_baseline("margin_pct", observed_value=0.25, sample_size=8)
    significance = assess_significance(baseline, current_value=0.10, impact_thresholds=(0.05, 0.10))

    # Each dimension is independently inspectable -- not merged into one number.
    fields = vars(significance)
    assert {"deviation", "impact", "urgency", "persistence", "recurrence_count", "correlation",
            "strategic_relevance", "confidence"} <= set(fields)


def test_confidence_is_inherited_from_the_baseline():
    insufficient = build_baseline("margin_pct", observed_value=None, sample_size=0)
    significance = assess_significance(insufficient, current_value=None, impact_thresholds=(0.05, 0.10))

    assert significance.confidence == insufficient.confidence
    assert significance.deviation is None


def test_correlation_and_strategic_relevance_are_passed_through():
    baseline = build_baseline("margin_pct", observed_value=0.25, sample_size=8)
    significance = assess_significance(
        baseline,
        current_value=0.10,
        impact_thresholds=(0.05, 0.10),
        correlation=["SupplierCostIncreased on Northline Steel"],
        strategic_relevance="high",
    )

    assert significance.correlation == ["SupplierCostIncreased on Northline Steel"]
    assert significance.strategic_relevance == "high"
