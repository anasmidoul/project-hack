"""Unit A7 — model gateway: the only way text reaches an AI model.

Contract: DESIGN.md section 7 (privacy.py and llm.py).

Never import `openai` (or any model SDK) at module top level; import it inside `complete`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class LLMError(Exception):
    """Raised on any failure to get an answer from the model."""


def complete(system: str, user: str, known: Mapping[str, str] | None = None) -> str:
    """Ask the model and return its answer with real values restored.

    1. masked = privacy.mask(user, known)
    2. privacy.assert_clean(masked.text, masked.mapping)
    3. call the model with system + masked.text
    4. return privacy.unmask(answer, masked.mapping)

    Raises LLMError on any failure. `system` must be fixed text with no personal data.
    """
    raise NotImplementedError("A7: llm.complete")
