"""Unit A2 — Idealista probe (DESIGN.md section 8, A2; PLAN.md step 0).

    uv run python scripts/idealista_probe.py            # check the inbox on the saved profile
    uv run python scripts/idealista_probe.py --login    # open the login page, log in by hand once

The check opens config.IDEALISTA_INBOX_URL in a local Chromium on config.CHROME_PROFILE_DIR and
reports whether the page loaded, whether it looks logged in, roughly how many conversations it
sees and the final URL. It uses no AI model, sends nothing and prints no names or message text.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from housia import config  # noqa: E402

DEFAULT_LOGIN_URL = "https://www.idealista.com/login"

# Counts links that look like conversations, and signs of a login page. Returns numbers only.
_PAGE_SUMMARY_JS = """
(() => {
  const inbox = new URL(%s);
  const base = inbox.pathname.replace(/\\/+$/, '');
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    let u;
    try { u = new URL(a.href, location.href); } catch (e) { continue; }
    if (u.host !== location.host) continue;
    const p = u.pathname.replace(/\\/+$/, '');
    const underInbox = base && p.startsWith(base + '/') && !p.endsWith('/send');
    const looksLikeConversation = /conversa|conversation|mensaje|message|chat/i.test(p) && /\\d/.test(p + u.search);
    if (underInbox || looksLikeConversation) seen.add(p + u.search);
  }
  const password = document.querySelectorAll('input[type=password]').length;
  return JSON.stringify({
    ready: document.readyState,
    url: location.href,
    conversations: seen.size,
    password_fields: password,
    has_body: !!(document.body && document.body.innerText.trim().length),
  });
})()
"""

_LOGIN_WORDS = ("login", "signin", "sign-in", "acceso", "iniciar-sesion", "auth")


def _missing_settings(need_model: bool) -> list[str]:
    problems = []
    if not config.IDEALISTA_INBOX_URL or not urlsplit(config.IDEALISTA_INBOX_URL).hostname:
        problems.append("IDEALISTA_INBOX_URL is missing or not a URL (e.g. https://www.idealista.com/...)")
    if not config.CHROME_PROFILE_DIR:
        problems.append("CHROME_PROFILE_DIR is missing (e.g. ~/housia-profile)")
    if need_model:
        if not config.BROWSER_MODEL:
            problems.append("BROWSER_MODEL is missing (the OpenAI model that drives the browser)")
        if not config.OPENAI_API_KEY:
            problems.append("OPENAI_API_KEY is missing")
    return problems


def _host_allowed(host: str) -> bool:
    for entry in config.BROWSER_ALLOWED_DOMAINS:
        entry = entry.split("://")[-1].split("/")[0].split(":")[0].lower()
        if entry.startswith("*."):
            entry = entry[2:]
        if host == entry or host == "www." + entry or host.endswith("." + entry):
            return True
    return False


async def _open(headless: bool | None, domains: list[str] | None):
    from browser_use import Browser

    browser = Browser("chromium", user_data_dir=config.CHROME_PROFILE_DIR, headless=headless,
                      allowed_domains=domains)
    await browser.start()
    # browser-harness helpers talk to the daemon named in BU_NAME, read when they are imported.
    os.environ["BU_NAME"] = browser.name
    from browser_harness import helpers

    return browser, helpers


async def _login(url: str) -> int:
    print(f"Opening {url} on the profile {config.CHROME_PROFILE_DIR}.")
    browser, helpers = await _open(headless=False, domains=None)
    try:
        await asyncio.to_thread(helpers.goto_url, url)
        print("Log in by hand in the browser window. HOUSIA does not type your password.")
        await asyncio.to_thread(input, "When you are logged in, press Enter here to close the browser... ")
    finally:
        await browser.stop()
    print("Browser closed. The login is saved in the profile. Now run the probe without --login.")
    return 0


async def _probe(wait_sec: float) -> int:
    url = config.IDEALISTA_INBOX_URL
    host = (urlsplit(url).hostname or "").lower()
    print(f"Inbox URL : {url}")
    print(f"Profile   : {config.CHROME_PROFILE_DIR}")
    if not _host_allowed(host):
        print(f"Note      : '{host}' is not in BROWSER_ALLOWED_DOMAINS "
              f"({', '.join(config.BROWSER_ALLOWED_DOMAINS) or 'empty'}). The channel's agent will be "
              "blocked there; add the portal's domain before running the worker.")
    browser, helpers = await _open(headless=None, domains=None)
    try:
        await asyncio.to_thread(helpers.goto_url, url)
        await asyncio.to_thread(helpers.wait_for_load, 20.0)
        await asyncio.sleep(wait_sec)  # client-side rendered inboxes fill in after load
        deadline = time.monotonic() + 10
        summary = {}
        while time.monotonic() < deadline:
            raw = await asyncio.to_thread(helpers.js, _PAGE_SUMMARY_JS % json.dumps(url))
            summary = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if summary.get("ready") == "complete":
                break
            await asyncio.sleep(0.5)
    finally:
        await browser.stop()

    final_url = summary.get("url", "")
    loaded = summary.get("ready") == "complete" and bool(summary.get("has_body"))
    path = urlsplit(final_url).path.lower()
    on_login = any(word in path for word in _LOGIN_WORDS) or summary.get("password_fields", 0) > 0
    logged_in = loaded and not on_login
    print(f"Loaded    : {'yes' if loaded else 'no'}")
    print(f"Logged in : {'looks like yes' if logged_in else 'looks like NO (login page or password field seen)'}")
    print(f"Conversations seen (link count, approximate): {summary.get('conversations', 0)}")
    print(f"Final URL : {final_url}")
    if not logged_in:
        print("Next step : uv run python scripts/idealista_probe.py --login, log in by hand, run the probe again.")
    return 0 if logged_in else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check the Idealista inbox on the saved browser profile. Sends nothing and "
                    "prints no names or message text.")
    parser.add_argument("--login", nargs="?", const=DEFAULT_LOGIN_URL, metavar="URL",
                        help="only open the browser on the profile at the portal's login page "
                             f"(default {DEFAULT_LOGIN_URL}) so you can log in by hand; "
                             "closes when you press Enter")
    parser.add_argument("--wait", type=float, default=3.0, metavar="SEC",
                        help="extra seconds to let the inbox render before counting (default 3)")
    args = parser.parse_args()

    problems = _missing_settings(need_model=False)
    if problems:
        print("Cannot run the probe. Set these in .env (see .env.example):")
        for p in problems:
            print(f"  - {p}")
        sys.exit(2)
    model_problems = _missing_settings(need_model=True)
    if model_problems and not args.login:
        print("Note: the probe itself needs no model, but the Idealista channel will. Missing:")
        for p in model_problems:
            print(f"  - {p}")

    try:
        code = asyncio.run(_login(args.login) if args.login else _probe(args.wait))
    except KeyboardInterrupt:
        code = 130
    except Exception as e:
        print(f"Probe failed: {type(e).__name__}: {e}")
        print("If Chromium is missing, run once: uv run browser-use install")
        print("If the profile is in use, close the other browser window that uses it.")
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
