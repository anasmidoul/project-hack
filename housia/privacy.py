"""Unit A7 — privacy guard: mask personal data before it reaches a model.

Contract: DESIGN.md section 7 (privacy.py and llm.py).

Purpose: no real name, contact detail or identity number leaves the machine in a model request.
Values are replaced with placeholders before the call and put back afterwards. The table that
links placeholders to real values exists only in memory for that one call.

What `mask` replaces:
- Known values from the database (`known`): the applicant's full name and each part of it,
  email and phone. Matched without regard to case or accents.
- Patterns: email addresses; phone numbers (Spanish 9-digit and +34); DNI (8 digits and a
  letter); NIE (X, Y or Z, 7 digits, a letter); passport numbers (3 letters and 6 digits); IBAN;
  payment card numbers; any other run of 8 or more digits.
- Labelled fields in documents: the value after labels such as Name:, Full name:, Nombre:,
  DNI:, NIE:, Passport:, IBAN:, Address:, Dirección:.

Placeholders look like [NAME_1], [ID_1], [IBAN_1], [PHONE_1], [EMAIL_1], [NUMBER_1]. The same
value gets the same placeholder within one call, so the model can still reason.

Known limits:
- A name that is not in the database and not next to a label (for example a flatmate mentioned
  in free text) is not detected.
- The browser agent (A2) looks at the portal page as it is, with real names and messages on
  screen. Masking cannot apply there. See DESIGN.md section 8.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class PrivacyError(Exception):
    """Raised when a real value would still reach a model."""


@dataclass
class Masked:
    text: str
    mapping: dict[str, str]        # placeholder -> real value. Never stored, logged or sent.


def known_values(application: Mapping) -> dict[str, str]:
    """Return {'NAME': ..., 'EMAIL': ..., 'PHONE': ...} for an application."""
    raise NotImplementedError("A7: privacy.known_values")


def mask(text: str, known: Mapping[str, str] | None = None) -> Masked:
    """Replace known values, patterns and labelled fields in text with placeholders."""
    raise NotImplementedError("A7: privacy.mask")


def unmask(text: str, mapping: dict[str, str]) -> str:
    """Put the real values back in place of the placeholders."""
    raise NotImplementedError("A7: privacy.unmask")


def assert_clean(text: str, mapping: dict[str, str]) -> None:
    """Raise PrivacyError if a real value is still in text."""
    raise NotImplementedError("A7: privacy.assert_clean")
