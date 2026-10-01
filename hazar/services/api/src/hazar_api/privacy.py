"""PII helpers. Anything that might reach logs, analytics or an external LLM goes through here."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable
from dataclasses import dataclass


def mask_phone(phone: str) -> str:
    """'+972501234567' -> '+9725*****67'. Safe for logs."""
    if len(phone) < 6:
        return "***"
    return phone[:5] + "*" * (len(phone) - 7) + phone[-2:]


def keyed_hash(secret: bytes, value: str) -> str:
    """Stable, non-reversible identifier for PII used in cache keys and rate-limit buckets."""
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


# --- masking before any external LLM call (CLAUDE.md principle 5) -------------------------------------------
#
# Deliberately over-masks: a false positive costs a little context, a false negative leaks PII.
# Every LLM call must pass its text through mask_for_llm first (agents arrive in Sprint 7).

_D = r"(?<![\d\w])"  # left boundary: not preceded by a digit/letter
_E = r"(?![\d\w])"  # right boundary

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[IBAN]", re.compile(_D + r"IL\d{2}(?:[ -]?\d{4}){4}[ -]?\d{3}" + _E, re.IGNORECASE)),
    ("[CARD]", re.compile(_D + r"\d{4}(?:[ -]?\d{4}){2}[ -]?\d{1,7}" + _E)),
    ("[PHONE]", re.compile(_D + r"(?:\+972[ -]?|0)(?:5\d|[2-489]|7\d)[ -]?\d{3}[ -]?\d{4}" + _E)),
    # bank-branch-account, e.g. 12-345-678901
    ("[BANK_ACCOUNT]", re.compile(_D + r"\d{2,3}[ -/]\d{3}[ -/]\d{4,9}" + _E)),
    # account number after a keyword, e.g. "חשבון 1234567", "ח-ן: 55-1234", "account no. 123456"
    (
        "[BANK_ACCOUNT]",
        re.compile(
            r"(?:(?<=חשבון)|(?<=ח-ן)|(?<=ח\"ן)|(?<=account)|(?<=acct))(?:\s*(?:מס'|מספר|no\.?|number|#|:))*\s*"
            r"\d[\d -]{3,16}\d",
            re.IGNORECASE,
        ),
    ),
    # Israeli ID (ת"ז): 8–9 digits, optionally with a dash before the check digit
    ("[ID]", re.compile(_D + r"\d{7,8}[ -]?\d" + _E)),
]


@dataclass(frozen=True)
class MaskResult:
    text: str
    counts: dict[str, int]


def mask_for_llm(text: str, names: Iterable[str] = ()) -> MaskResult:
    """Replace ID numbers, bank/IBAN/card numbers, phones, emails and the given full/partial names."""
    counts: dict[str, int] = {}
    for placeholder, pattern in _PATTERNS:
        text, n = pattern.subn(placeholder, text)
        if n:
            counts[placeholder] = counts.get(placeholder, 0) + n
    for name in sorted({n.strip() for n in names if len(n.strip()) >= 2}, key=len, reverse=True):
        pattern = re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", re.IGNORECASE)
        text, n = pattern.subn("[NAME]", text)
        if n:
            counts["[NAME]"] = counts.get("[NAME]", 0) + n
    return MaskResult(text, counts)
