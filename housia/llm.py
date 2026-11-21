"""Unit A7 — model gateway: the only way text reaches an AI model.

Contract: DESIGN.md section 7 (privacy.py and llm.py).

Never import `openai` (or any model SDK) at module top level; import it inside `_call_model`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from housia import config, privacy

if TYPE_CHECKING:
    from collections.abc import Mapping

_TIMEOUT_SEC = 60


class LLMError(Exception):
    """Raised on any failure to get an answer from the model."""


def _call_model(system: str, user: str) -> str:
    """Send one system + user text request to OpenAI and return the answer text.

    The only place that talks to the SDK; tests replace it with a fake.
    Uses the Responses API (openai 3.x): `instructions` is the system message, `input` the
    user text. `store=False` so OpenAI does not keep the request for later retrieval.
    """
    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY, timeout=_TIMEOUT_SEC, max_retries=1)
    response = client.responses.create(
        model=config.REPLY_MODEL,
        instructions=system,
        input=user,
        store=False,
    )
    return response.output_text


def complete(system: str, user: str, known: Mapping[str, str] | None = None) -> str:
    """Ask the model and return its answer with real values restored.

    1. masked = privacy.mask(user, known)
    2. privacy.assert_clean(masked.text, masked.mapping)
    3. call the model with system + masked.text
    4. return privacy.unmask(answer, masked.mapping)

    Raises LLMError on any failure. `system` must be fixed text with no personal data.
    """
    if (config.LLM_PROVIDER or "openai") != "openai":
        raise LLMError(f"unsupported LLM_PROVIDER: {config.LLM_PROVIDER}")
    if not config.REPLY_MODEL:
        raise LLMError("REPLY_MODEL is not set")
    if not config.OPENAI_API_KEY:
        raise LLMError("OPENAI_API_KEY is not set")

    try:
        masked = privacy.mask(user, known)
        privacy.assert_clean(masked.text, masked.mapping)
    except privacy.PrivacyError as e:
        raise LLMError(f"masking failed: {e}") from e
    except Exception as e:
        raise LLMError(f"masking failed: {type(e).__name__}") from None

    try:
        answer = _call_model(system, masked.text)
    except Exception as e:  # SDK errors, network, timeouts, missing package
        # Only the error type: the message could echo the request.
        raise LLMError(f"model call failed: {type(e).__name__}") from None

    if not isinstance(answer, str) or not answer.strip():
        raise LLMError("model returned an empty answer")
    return privacy.unmask(answer, masked.mapping)
