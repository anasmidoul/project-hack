"""Configuration, read from the environment (and `.env`) when this module is imported.

Other modules read `config.X` at call time, so tests can monkeypatch values.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

# browser-use sends usage telemetry to its own servers by default, including the final result
# of each agent run. Our results hold names and message text of real people, so it is forced
# off here, before browser-use can be imported. Do not make this configurable.
os.environ["ANONYMIZED_TELEMETRY"] = "false"


def _str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _int(name: str, default: int) -> int:
    value = _str(name)
    return int(value) if value is not None else default


def _list(name: str, default: str = "") -> list[str]:
    value = _str(name, default) or ""
    return [item.strip() for item in value.split(",") if item.strip()]


HOUSIA_DB: str = _str("HOUSIA_DB", "instance/housia.db")
PORT: int = _int("PORT", 5000)
BASE_URL: str = _str("BASE_URL", "http://localhost:5000")
CHANNEL: str = _str("CHANNEL", "mock")
DEFAULT_PROPERTY_ID: int = _int("DEFAULT_PROPERTY_ID", 1)
WORKER_INTERVAL_SEC: int = _int("WORKER_INTERVAL_SEC", 20)
REPLY_ENGINE: str = _str("REPLY_ENGINE", "template")
LLM_PROVIDER: str = _str("LLM_PROVIDER", "openai")
REPLY_MODEL: str | None = _str("REPLY_MODEL")
BROWSER_MODEL: str | None = _str("BROWSER_MODEL")
SEND_ALLOWLIST: list[str] = _list("SEND_ALLOWLIST")
CHROME_PROFILE_DIR: str = os.path.expanduser(_str("CHROME_PROFILE_DIR", "~/housia-profile"))
IDEALISTA_INBOX_URL: str = _str("IDEALISTA_INBOX_URL", "http://localhost:5000/mock/inbox")
BROWSER_ALLOWED_DOMAINS: list[str] = _list("BROWSER_ALLOWED_DOMAINS", "localhost")
OPENAI_API_KEY: str | None = _str("OPENAI_API_KEY")
SECRET_KEY: str = _str("SECRET_KEY", "dev")
# Optional local demo data loaded after the seed on reset (see housia/demo_extra.py).
DEMO_EXTRA_FILE: str = _str("DEMO_EXTRA_FILE", "instance/demo_extra.json")
OWNER_PASSWORD: str | None = _str("OWNER_PASSWORD")
WORKSPACE_AI_NOTES: bool = _str("WORKSPACE_AI_NOTES", "0") == "1"
