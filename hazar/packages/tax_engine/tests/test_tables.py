from __future__ import annotations

from pathlib import Path

import pytest

from hazar_tax_engine import UnverifiedTablesError, load_tables, parse_tables
from hazar_tax_engine.tables import TABLES_DIR


def test_template_parses_and_is_unverified() -> None:
    tables = parse_tables((TABLES_DIR / "_template.yaml").read_text(encoding="utf-8"))
    assert not tables.is_verified
    with pytest.raises(UnverifiedTablesError):
        tables.require_verified()


def test_single_unverified_entry_blocks_final_result() -> None:
    tables = parse_tables(
        """
year: 2000
tables_version: test-1
values:
  a: {value: 1, verified: true}
  b: {value: 2, verified: false}
"""
    )
    with pytest.raises(UnverifiedTablesError) as err:
        tables.require_verified()
    assert err.value.keys == ["b"]


def test_verified_entry_without_value_counts_as_unverified() -> None:
    tables = parse_tables("year: 2000\ntables_version: t\nvalues:\n  a: {value: null, verified: true}\n")
    assert tables.unverified_keys() == ["a"]


def test_fully_verified_tables_pass() -> None:
    tables = parse_tables("year: 2000\ntables_version: t\nvalues:\n  a: {value: 1, verified: true}\n")
    tables.require_verified()


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValueError):
        parse_tables("year: 2000\ntables_version: t\nvalues: {}\nsurprise: 1\n")


def test_missing_year_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tables(2000, tmp_path)


def test_year_mismatch(tmp_path: Path) -> None:
    (tmp_path / "2001.yaml").write_text("year: 2000\ntables_version: t\nvalues: {}\n")
    with pytest.raises(ValueError, match="declares year"):
        load_tables(2001, tmp_path)


def test_no_real_year_tables_committed_yet() -> None:
    """Sprint 1 guard: real year tables arrive only with advisor verification (Sprint 3)."""
    assert sorted(p.name for p in TABLES_DIR.glob("*.yaml")) == ["_template.yaml"]
