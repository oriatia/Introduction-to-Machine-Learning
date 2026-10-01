from __future__ import annotations

import re

_MOBILE = re.compile(r"^5\d{8}$")


class InvalidPhoneError(ValueError):
    pass


def normalize_il_mobile(raw: str) -> str:
    """Normalize an Israeli mobile number (050-1234567, +972 50 123 4567, ...) to E.164."""
    digits = re.sub(r"[\s\-().]", "", raw)
    if digits.startswith("+972"):
        local = digits[4:]
    elif digits.startswith("00972"):
        local = digits[5:]
    elif digits.startswith("972"):
        local = digits[3:]
    elif digits.startswith("0"):
        local = digits[1:]
    else:
        raise InvalidPhoneError("unsupported phone format")
    if not _MOBILE.fullmatch(local):
        raise InvalidPhoneError("not an Israeli mobile number")
    return f"+972{local}"
