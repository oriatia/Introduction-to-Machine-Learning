"""Deterministic Israeli income tax engine.

Pure Python: no network, no database. The only I/O is reading this package's own year tables.
No tax value may appear in code; all values come from `tables/{year}.yaml`.
"""

from hazar_tax_engine.registry import RULES, RULES_BY_ID, DocumentType, Fact, Rule, required_facts
from hazar_tax_engine.screening import (
    REFUND_WINDOW_YEARS,
    Finding,
    LocalityPeriod,
    ScreeningInput,
    ScreeningResult,
    refund_window,
    screen,
)
from hazar_tax_engine.tables import (
    TableEntry,
    UnverifiedTablesError,
    YearTables,
    load_tables,
    parse_tables,
)

ENGINE_VERSION = "0.2.0"

__all__ = [
    "ENGINE_VERSION",
    "REFUND_WINDOW_YEARS",
    "RULES",
    "RULES_BY_ID",
    "DocumentType",
    "Fact",
    "Finding",
    "LocalityPeriod",
    "Rule",
    "ScreeningInput",
    "ScreeningResult",
    "TableEntry",
    "UnverifiedTablesError",
    "YearTables",
    "load_tables",
    "parse_tables",
    "refund_window",
    "required_facts",
    "screen",
]
