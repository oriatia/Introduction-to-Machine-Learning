from __future__ import annotations

from datetime import date

from hazar_tax_engine import (
    RULES,
    Fact,
    LocalityPeriod,
    ScreeningInput,
    refund_window,
    required_facts,
    screen,
)

TODAY = date(2026, 10, 1)
WINDOW = [2020, 2021, 2022, 2023, 2024, 2025]


def by_rule(facts: ScreeningInput) -> dict[str, list[int]]:
    return {f.rule_id: f.years for f in screen(facts, TODAY).findings}


def test_window_is_six_completed_years() -> None:
    assert refund_window(TODAY) == WINDOW
    assert refund_window(date(2027, 1, 1)) == [2021, 2022, 2023, 2024, 2025, 2026]


def test_registry_is_consistent() -> None:
    ids = [r.rule_id for r in RULES]
    assert len(ids) == len(set(ids))
    assert required_facts() == set(Fact)  # every fact is used by some rule, and no rule needs an unknown fact
    for rule in RULES:
        assert rule.title_he and rule.explanation_he
        assert rule.documents
        # Until the advisor verifies them, legal references must not be presented as verified.
        assert not (rule.legal_ref_verified and rule.legal_ref is None)


def test_no_facts_no_findings() -> None:
    result = screen(ScreeningInput(resident=True, sex="female", marital_status="single"), TODAY)
    assert result.findings == []
    assert result.is_estimate is True
    assert result.window == WINDOW


def test_baseline_rules_are_never_findings() -> None:
    rules = by_rule(ScreeningInput(resident=True, sex="female"))
    assert "credit.resident" not in rules
    assert "credit.woman" not in rules


def test_children_from_birth_year() -> None:
    rules = by_rule(ScreeningInput(child_birth_dates=[date(2023, 5, 1), date(2025, 2, 1)]))
    assert rules["credit.children"] == [2023, 2024, 2025]
    assert "credit.single_parent" not in rules


def test_child_born_before_window_covers_whole_window() -> None:
    assert by_rule(ScreeningInput(child_birth_dates=[date(2010, 1, 1)]))["credit.children"] == WINDOW


def test_child_born_this_year_has_no_completed_year_yet() -> None:
    assert "credit.children" not in by_rule(ScreeningInput(child_birth_dates=[date(2026, 3, 1)]))


def test_single_parent_requires_children() -> None:
    assert "credit.single_parent" not in by_rule(ScreeningInput(single_parent=True))
    rules = by_rule(ScreeningInput(single_parent=True, child_birth_dates=[date(2021, 1, 1)]))
    assert rules["credit.single_parent"] == [2021, 2022, 2023, 2024, 2025]


def test_life_events_open_years_from_their_date() -> None:
    rules = by_rule(
        ScreeningInput(
            degree_completion_years=[2022],
            discharge_date=date(2019, 8, 1),
            aliyah_date=date(2024, 6, 1),
            disability=True,
        )
    )
    assert rules["credit.academic_degree"] == [2022, 2023, 2024, 2025]
    assert rules["credit.discharged_soldier"] == WINDOW
    assert rules["credit.new_immigrant"] == [2024, 2025]
    assert rules["credit.disability"] == WINDOW


def test_year_lists_are_clipped_to_window() -> None:
    rules = by_rule(
        ScreeningInput(
            multiple_employer_years=[2015, 2021, 2021, 2026],
            donation_years=[2019],
            partial_years=[2025],
        )
    )
    assert rules["income.multiple_employers"] == [2021]
    assert "deduction.donations" not in rules
    assert rules["income.partial_year"] == [2025]


def test_localities() -> None:
    rules = by_rule(
        ScreeningInput(
            localities=[
                LocalityPeriod(name="א", from_year=2015, to_year=2021),
                LocalityPeriod(name="ב", from_year=2024),
            ]
        )
    )
    assert rules["credit.eligible_locality"] == [2020, 2021, 2024, 2025]


def test_findings_carry_documents_and_no_amounts() -> None:
    finding = screen(ScreeningInput(donation_years=[2023]), TODAY).findings[0]
    assert finding.documents == ["donation_receipt"]
    assert finding.legal_ref is None
    assert not finding.legal_ref_verified
    assert "amount" not in finding.model_dump()


def test_screening_is_deterministic() -> None:
    facts = ScreeningInput(child_birth_dates=[date(2022, 1, 1)], donation_years=[2024], disability=True)
    assert screen(facts, TODAY) == screen(facts, TODAY)
