from __future__ import annotations

import pytest

from hazar_api.privacy import mask_for_llm


@pytest.mark.parametrize(
    ("text", "placeholder"),
    [
        ("ת.ז. 123456782", "[ID]"),
        ('מס׳ ת"ז: 12345678-2 בבקשה', "[ID]"),
        ("ID 01234567", "[ID]"),
        ("טלפון 050-1234567", "[PHONE]"),
        ("call +972 52 123 4567", "[PHONE]"),
        ("קווי 03-6123456", "[PHONE]"),
        ("IBAN IL62 0108 0000 0009 9999 999", "[IBAN]"),
        ("il620108000000099999999", "[IBAN]"),
        ("בנק 12-345-678901", "[BANK_ACCOUNT]"),
        ("מספר חשבון 4567890", "[BANK_ACCOUNT]"),
        ("account no. 55-1234", "[BANK_ACCOUNT]"),
        ("כרטיס 4580 1234 5678 9012", "[CARD]"),
        ("mail me: dana.levi+tax@example.co.il", "[EMAIL]"),
    ],
)
def test_masks_pii(text: str, placeholder: str) -> None:
    result = mask_for_llm(text)
    assert placeholder in result.text, result.text
    assert not any(ch.isdigit() for ch in result.text.split(placeholder)[0][-1:])


def test_original_digits_do_not_survive() -> None:
    text = "ת.ז 123456782, חשבון 12-345-678901, טלפון 0501234567"
    out = mask_for_llm(text).text
    for secret in ("123456782", "678901", "1234567"):
        assert secret not in out


def test_names_are_masked_longest_first_with_word_boundaries() -> None:
    result = mask_for_llm("דנה לוי ובעלה משה לוי. דנהלה לא.", names=["דנה לוי", "משה", "לוי"])
    assert result.text == "[NAME] ובעלה [NAME] [NAME]. דנהלה לא."
    assert result.counts["[NAME]"] == 3


def test_tax_content_is_kept() -> None:
    text = "בשנת 2023 ההכנסה הייתה 184,500 ש״ח והמס שנוכה 21,340. נקודות זיכוי: 2.25. סעיף 46."
    result = mask_for_llm(text)
    assert result.text == text
    assert result.counts == {}


def test_counts() -> None:
    result = mask_for_llm("123456782 ו-987654321")
    assert result.counts == {"[ID]": 2}
