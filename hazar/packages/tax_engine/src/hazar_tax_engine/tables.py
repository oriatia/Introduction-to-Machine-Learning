from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

TABLES_DIR = Path(__file__).resolve().parents[2] / "tables"


class UnverifiedTablesError(Exception):
    """Raised when a final result is requested for a year whose tables contain unverified values."""

    def __init__(self, year: int | None, keys: list[str]) -> None:
        self.year = year
        self.keys = keys
        super().__init__(f"Tables for {year} contain unverified values: {', '.join(keys)}")


class TableEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Any = None
    verified: bool = False
    todo: str | None = None


class YearTables(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int | None
    tables_version: str | None
    source: str | None = None
    reviewed_by: str | None = None
    values: dict[str, TableEntry]

    def unverified_keys(self) -> list[str]:
        return sorted(k for k, e in self.values.items() if not e.verified or e.value is None)

    @property
    def is_verified(self) -> bool:
        return not self.unverified_keys() and self.tables_version is not None

    def require_verified(self) -> None:
        """Guard for final results. Estimates may skip this but must be labelled `is_estimate`."""
        keys = self.unverified_keys()
        if self.tables_version is None:
            keys = ["tables_version", *keys]
        if keys:
            raise UnverifiedTablesError(self.year, keys)


def parse_tables(raw: str) -> YearTables:
    return YearTables.model_validate(yaml.safe_load(raw))


def load_tables(year: int, tables_dir: Path = TABLES_DIR) -> YearTables:
    path = tables_dir / f"{year}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"No tax tables for {year}. Add {path.name} from the official reference table."
        )
    tables = parse_tables(path.read_text(encoding="utf-8"))
    if tables.year != year:
        raise ValueError(f"{path.name} declares year {tables.year}")
    return tables
