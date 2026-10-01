from __future__ import annotations

import pytest

from hazar_api.config import Settings
from hazar_api.documents import sniff_content_type
from hazar_api.extraction import (
    FORM_106_FIELDS,
    MockExtractor,
    empty_result,
    make_extractor,
    make_mock_png,
    normalize_confirmed,
)

WINDOW = [2020, 2021, 2022, 2023, 2024, 2025]


def test_no_identity_fields_are_extracted() -> None:
    names = {f.name for f in FORM_106_FIELDS}
    assert not names & {"id_number", "employee_id", "name", "full_name", "address", "bank_account"}
    # Box numbers stay unset until the advisor confirms them (ADR 0004 §5).
    assert all(f.form_code is None for f in FORM_106_FIELDS)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"RIFF\x00\x00\x00\x00WEBPrest", "image/webp"),
        (b"%PDF-1.7 rest", "application/pdf"),
        (b"<html>", None),
        (b"MZ\x90\x00", None),
    ],
)
def test_sniff(data: bytes, expected: str | None) -> None:
    assert sniff_content_type(data) == expected


async def test_mock_reads_fixture_values() -> None:
    png = make_mock_png({"tax_year": ("2023", 0.99), "tax_withheld": ("12000", 0.6)})
    assert sniff_content_type(png) == "image/png"
    result = await MockExtractor().extract(png, "image/png", "form_106")
    assert result.fields["tax_year"].value == "2023"
    assert result.fields["employer_name"].value is None
    assert set(result.low_confidence()) == {f.name for f in FORM_106_FIELDS} - {"tax_year"}


async def test_mock_on_real_photo_returns_empty_fields() -> None:
    result = await MockExtractor().extract(b"\xff\xd8\xff\xe0jpeg", "image/jpeg", "form_106")
    assert result == empty_result("form_106")
    assert all(f.confidence == 0 for f in result.fields.values())


def test_claude_requires_explicit_privacy_opt_in() -> None:
    with pytest.raises(RuntimeError, match="ADR 0004"):
        make_extractor(Settings(env="test", extraction_provider="claude"))
    assert make_extractor(Settings(env="test")).name == "mock"


def test_normalize_confirmed() -> None:
    values = normalize_confirmed(
        "form_106",
        {
            "tax_year": "2023",
            "employer_name": ' חברה בע"מ ',
            "employer_file_number": "912345678",
            "months_worked": 7,
            "gross_taxable_income": "184,500",
            "tax_withheld": "21340",
            "credit_points": "2.25",
            "pension_employee_deposit": "",
        },
        WINDOW,
    )
    assert values == {
        "tax_year": 2023,
        "employer_name": 'חברה בע"מ',
        "employer_file_number": "912345678",
        "months_worked": 7,
        "gross_taxable_income": 184500,
        "tax_withheld": 21340,
        "credit_points": 2.25,
        "pension_employee_deposit": None,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tax_year", "2019"),
        ("tax_year", None),
        ("months_worked", "13"),
        ("gross_taxable_income", "-5"),
        ("gross_taxable_income", "12.5.3"),
        ("credit_points", "abc"),
        ("employer_file_number", "12a"),
    ],
)
def test_normalize_rejects(field: str, value: object) -> None:
    raw: dict[str, object] = {"tax_year": "2023", field: value}
    with pytest.raises(ValueError, match=field):
        normalize_confirmed("form_106", raw, WINDOW)
