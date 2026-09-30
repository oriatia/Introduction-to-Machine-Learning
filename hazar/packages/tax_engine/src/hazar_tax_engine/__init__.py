"""Deterministic Israeli income tax engine.

Pure Python: no network, no database. The only I/O is reading this package's own year tables.
No tax value may appear in code; all values come from `tables/{year}.yaml`.
"""

from hazar_tax_engine.tables import (
    TableEntry,
    UnverifiedTablesError,
    YearTables,
    load_tables,
    parse_tables,
)

ENGINE_VERSION = "0.1.0"

__all__ = [
    "ENGINE_VERSION",
    "TableEntry",
    "UnverifiedTablesError",
    "YearTables",
    "load_tables",
    "parse_tables",
]
