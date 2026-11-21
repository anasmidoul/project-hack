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
value gets the same placeholder within one call, so the model can still reason. Variants that
differ only in case, accents or spacing count as the same value; `unmask` restores the first
form seen, so `unmask(mask(x)) == x` holds exactly when each value is written one way.
Labelled addresses use [ADDRESS_1] and card numbers [CARD_1].

Order: labelled fields, then email addresses, then known and labelled values everywhere else in
the text (longest first, so a full name is replaced before its parts), then the other patterns.
Text already replaced by a placeholder is never matched again.

Known limits:
- A name that is not in the database and not next to a label (for example a flatmate mentioned
  in free text) is not detected.
- A labelled value runs to the end of its line, so the rest of that line is masked too.
- Foreign phone numbers are only caught when written with a leading + or as 8+ digits.
- The browser agent (A2) looks at the portal page as it is, with real names and messages on
  screen. Masking cannot apply there. See DESIGN.md section 8.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class PrivacyError(Exception):
    """Raised when a real value would still reach a model."""


@dataclass
class Masked:
    text: str
    mapping: dict[str, str]        # placeholder -> real value. Never stored, logged or sent.


_PLACEHOLDER = re.compile(r"\[[A-Z]+_\d+\]")

# Short words that often sit inside Spanish names; never masked on their own.
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e", "da", "do", "dos", "van", "von", "di"}

_LABEL_KINDS = {
    "full name": "NAME", "name": "NAME", "nombre y apellidos": "NAME", "nombre completo": "NAME",
    "nombre": "NAME", "apellidos": "NAME",
    "dni": "ID", "nie": "ID", "nif": "ID", "passport": "ID", "pasaporte": "ID",
    "iban": "IBAN",
    "address": "ADDRESS", "direccion": "ADDRESS", "domicilio": "ADDRESS",
}
# Run on accent-folded, lower-cased text. Longer labels first.
_LABELS = re.compile(
    r"(?m)(?<!\w)(" + "|".join(sorted((re.escape(k) for k in _LABEL_KINDS), key=len, reverse=True))
    + r")[ \t]*:[ \t]*(\S[^\n\r]*?)[ \t]*$"
)

# (kind, pattern) in the order they run.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]{4}){3,7}(?:[ -]?[A-Z0-9]{1,3})?\b")),
    ("ID", re.compile(r"\b[XYZxyz][ -]?\d{7}[ -]?[A-Za-z]\b")),           # NIE
    ("ID", re.compile(r"\b\d{8}[ -]?[A-Za-z]\b")),                          # DNI
    ("ID", re.compile(r"\b[A-Z]{3}\d{6}\b")),                               # passport
    ("CARD", re.compile(r"(?<![\w+])\d(?:[ -]?\d){12,18}(?!\w)")),         # 13-19 digits
    ("PHONE", re.compile(r"(?<![\w+])(?:(?:\+|00)34[\s.-]?)?[6789](?:[\s.-]?\d){8}(?!\w)")),
    ("PHONE", re.compile(r"(?<![\w+])\+\d{1,3}(?:[\s.-]?\d){6,12}(?!\w)")),
    ("NUMBER", re.compile(r"\d{8,}")),
]


def _fold(text: str) -> str:
    """Lower-case and strip accents, keeping one character per character of `text`."""
    out = []
    for ch in text:
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        low = base.lower()
        out.append(low if len(low) == 1 else ch)
    return "".join(out)


@dataclass
class _State:
    mapping: dict[str, str] = field(default_factory=dict)      # placeholder -> value
    by_value: dict[str, str] = field(default_factory=dict)     # folded value -> placeholder
    counts: dict[str, int] = field(default_factory=dict)

    def placeholder(self, kind: str, value: str) -> str:
        # Variants in case, accents or spacing share one placeholder; the first form seen is
        # the one `unmask` puts back.
        key = " ".join(_fold(value).split())
        if key in self.by_value:
            return self.by_value[key]
        n = self.counts.get(kind, 0) + 1
        self.counts[kind] = n
        ph = f"[{kind}_{n}]"
        self.mapping[ph] = value
        self.by_value[key] = ph
        return ph


def _replace(
    text: str,
    regex: re.Pattern[str],
    kind: str | Callable[[re.Match[str]], str],
    state: _State,
    *,
    fold: bool = False,
    group: int = 0,
    found: list[tuple[str, str]] | None = None,
) -> str:
    """Replace matches of `regex` outside existing placeholders.

    With `fold`, the regex runs on the accent-folded lower-case text and the original
    characters at the same positions are what gets replaced.
    """
    parts = []
    pos = 0
    for ph in _PLACEHOLDER.finditer(text):
        parts.append(_replace_segment(text[pos:ph.start()], regex, kind, state, fold, group, found))
        parts.append(ph.group(0))
        pos = ph.end()
    parts.append(_replace_segment(text[pos:], regex, kind, state, fold, group, found))
    return "".join(parts)


def _replace_segment(segment, regex, kind, state, fold, group, found):
    if not segment:
        return segment
    haystack = _fold(segment) if fold else segment
    out = []
    pos = 0
    for m in regex.finditer(haystack):
        start, end = m.span(group)
        if start < pos or start == end:
            continue
        value = segment[start:end]
        k = kind(m) if callable(kind) else kind
        out.append(segment[pos:start])
        out.append(state.placeholder(k, value))
        if found is not None:
            found.append((k, value))
        pos = end
    out.append(segment[pos:])
    return "".join(out)


def _literal_regex(value: str, kind: str) -> re.Pattern[str] | None:
    """Regex that finds `value` in folded text as a whole word."""
    value = value.strip()
    if not value:
        return None
    if kind == "PHONE":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 6:
            return None
        body = r"[\s.-]*".join(digits)
        return re.compile(r"(?<![\w+])(?:\+?\d{1,3}[\s.-]*)?" + body + r"(?!\w)")
    words = _fold(value).split()
    body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)")


def _name_parts(name: str) -> list[str]:
    parts = re.split(r"[\s\-]+", name.strip())
    return [p for p in parts if len(p) >= 2 and _fold(p) not in _NAME_PARTICLES]


def known_values(application: Mapping) -> dict[str, str]:
    """Return {'NAME': ..., 'EMAIL': ..., 'PHONE': ...} for an application."""
    keys = application.keys()
    out: dict[str, str] = {}
    for kind, column in (("NAME", "name"), ("EMAIL", "email"), ("PHONE", "phone")):
        if column in keys:
            value = application[column]
            if value and str(value).strip():
                out[kind] = str(value).strip()
    return out


def mask(text: str, known: Mapping[str, str] | None = None) -> Masked:
    """Replace known values, patterns and labelled fields in text with placeholders."""
    state = _State()
    text = text or ""

    # 1. Labelled fields.
    labelled: list[tuple[str, str]] = []
    text = _replace(
        text, _LABELS, lambda m: _LABEL_KINDS[m.group(1)], state,
        fold=True, group=2, found=labelled,
    )

    # 2. Email addresses, so a name part is never matched inside one.
    email_kind, email_regex = _PATTERNS[0]
    text = _replace(text, email_regex, email_kind, state)

    # 3. Known and labelled values wherever else they appear, longest first.
    literals: dict[str, str] = {}   # value -> kind
    for kind, value in [*(known or {}).items(), *labelled]:
        if not value or not str(value).strip():
            continue
        kind = str(kind).upper()
        value = str(value).strip()
        literals.setdefault(value, kind)
        if kind == "NAME":
            for part in _name_parts(value):
                literals.setdefault(part, "NAME")
    for value, kind in sorted(literals.items(), key=lambda kv: len(kv[0]), reverse=True):
        regex = _literal_regex(value, kind)
        if regex is not None:
            text = _replace(text, regex, kind, state, fold=True)

    # 4. The other patterns.
    for kind, regex in _PATTERNS[1:]:
        text = _replace(text, regex, kind, state)

    return Masked(text=text, mapping=state.mapping)


def unmask(text: str, mapping: dict[str, str]) -> str:
    """Put the real values back in place of the placeholders."""
    if not text or not mapping:
        return text
    return _PLACEHOLDER.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


def assert_clean(text: str, mapping: dict[str, str]) -> None:
    """Raise PrivacyError if a real value is still in text."""
    folded = _fold(text or "")
    for placeholder, value in mapping.items():
        regex = _literal_regex(value, "")
        if regex is not None and regex.search(folded):
            # Never put the value itself in the message.
            raise PrivacyError(f"a value masked as {placeholder} is still in the text")
