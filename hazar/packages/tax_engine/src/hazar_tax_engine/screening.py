"""Screening: which rules MIGHT apply in which tax years, from the taxpayer's facts.

Relevance only. No ages, durations, caps, rates or amounts are encoded here; those live in verified per-year
tables and the Sprint 3+ engine. Every finding still needs the engine and the advisor.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hazar_tax_engine.registry import RULES_BY_ID, DocumentType, Rule

# CLAUDE.md: refunds cover up to 6 past tax years. Exact boundary to be confirmed by the advisor (ADR 0003).
REFUND_WINDOW_YEARS = 6


def refund_window(today: date) -> list[int]:
    """Completed tax years that may still be claimed, oldest first."""
    return list(range(today.year - REFUND_WINDOW_YEARS, today.year))


class LocalityPeriod(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    from_year: int
    to_year: int | None = None  # None = until today


class ScreeningInput(BaseModel):
    """Facts the screening reads. Built by the API from the user's profile and life events."""

    model_config = ConfigDict(frozen=True)

    resident: bool | None = None
    sex: Literal["female", "male"] | None = None
    marital_status: str | None = None
    single_parent: bool = False
    child_birth_dates: list[date] = Field(default_factory=list)
    degree_completion_years: list[int] = Field(default_factory=list)
    discharge_date: date | None = None
    aliyah_date: date | None = None
    disability: bool = False
    multiple_employer_years: list[int] = Field(default_factory=list)
    partial_years: list[int] = Field(default_factory=list)
    donation_years: list[int] = Field(default_factory=list)
    life_insurance_years: list[int] = Field(default_factory=list)
    pension_self_years: list[int] = Field(default_factory=list)
    localities: list[LocalityPeriod] = Field(default_factory=list)


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    title_he: str
    explanation_he: str
    years: list[int]
    documents: list[DocumentType]
    legal_ref: str | None
    legal_ref_verified: bool
    status: Literal["possible"] = "possible"


class ScreeningResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    window: list[int]
    findings: list[Finding]
    # Always true until amounts come from verified tables: the UI must not present this as a calculation.
    is_estimate: Literal[True] = True


def _from_year(start_year: int, window: list[int]) -> list[int]:
    return [y for y in window if y >= start_year]


def _in_window(years: list[int], window: list[int]) -> list[int]:
    return sorted({y for y in years if y in window})


def _finding(rule: Rule, years: list[int]) -> Finding:
    return Finding(
        rule_id=rule.rule_id,
        title_he=rule.title_he,
        explanation_he=rule.explanation_he,
        years=years,
        documents=list(rule.documents),
        legal_ref=rule.legal_ref,
        legal_ref_verified=rule.legal_ref_verified,
    )


def screen(facts: ScreeningInput, today: date) -> ScreeningResult:
    window = refund_window(today)
    candidates: dict[str, list[int]] = {}

    if facts.child_birth_dates:
        candidates["credit.children"] = _from_year(min(d.year for d in facts.child_birth_dates), window)
        if facts.single_parent:
            candidates["credit.single_parent"] = candidates["credit.children"]
    if facts.degree_completion_years:
        candidates["credit.academic_degree"] = _from_year(min(facts.degree_completion_years), window)
    if facts.discharge_date:
        candidates["credit.discharged_soldier"] = _from_year(facts.discharge_date.year, window)
    if facts.aliyah_date:
        candidates["credit.new_immigrant"] = _from_year(facts.aliyah_date.year, window)
    if facts.disability:
        candidates["credit.disability"] = list(window)
    candidates["income.multiple_employers"] = _in_window(facts.multiple_employer_years, window)
    candidates["income.partial_year"] = _in_window(facts.partial_years, window)
    candidates["deduction.donations"] = _in_window(facts.donation_years, window)
    candidates["deduction.life_insurance"] = _in_window(facts.life_insurance_years, window)
    candidates["deduction.pension_self"] = _in_window(facts.pension_self_years, window)
    if facts.localities:
        locality_years = {
            y
            for p in facts.localities
            for y in window
            if p.from_year <= y <= (p.to_year if p.to_year is not None else today.year)
        }
        candidates["credit.eligible_locality"] = sorted(locality_years)

    findings = [
        _finding(RULES_BY_ID[rule_id], years)
        for rule_id, years in candidates.items()
        if years and not RULES_BY_ID[rule_id].baseline
    ]
    return ScreeningResult(window=window, findings=findings)
