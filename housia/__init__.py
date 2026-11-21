"""HOUSIA web app factory."""

import secrets
from datetime import datetime
from urllib.parse import urlsplit

from flask import Flask, Response, abort, flash, g, redirect, request, session
from flask.sessions import SecureCookieSessionInterface

from housia import config, core, db

READ_ONLY_MESSAGE = "Read-only access: the judge login cannot change anything."
# The one change the read-only judge login may make: write as a candidate in the mock portal.
JUDGE_ALLOWED_POSTS = ("mock_inbox.candidate_send",)

# Headers that Cloudflare (cloudflared) always adds to a forwarded request. The app binds to
# 127.0.0.1, so a request carrying any of them came in through the public tunnel.
FORWARDING_HEADERS = ("Cf-Connecting-Ip", "Cf-Ray", "X-Forwarded-For")


def is_public_request(req) -> bool:
    """True when the request came through the public tunnel; False for a direct local request."""
    return any(name in req.headers for name in FORWARDING_HEADERS)


def _public_allowed(endpoint: str, path: str) -> bool:
    """What a public request may reach without the owner sign-in: applicant pages and forms,
    static files and the favicon."""
    return (
        endpoint in ("workspace.candidate", "static", "guest_link")
        or endpoint.startswith("applicant.")
        or path == "/favicon.ico"
    )


DEMO_FULL_PAGE = ("<!doctype html><meta charset=\"utf-8\"><title>HOUSIA demo</title>"
                  "<p style=\"font-family:sans-serif;margin:40px\">The demo is full, try again later.</p>")


def _demo_full() -> Response:
    return Response(DEMO_FULL_PAGE, 503, {"Content-Type": "text/html; charset=utf-8",
                                          "Retry-After": "600"})


def _is_https(req) -> bool:
    if req.is_secure:
        return True
    return is_public_request(req) and req.headers.get("X-Forwarded-Proto", "").lower() == "https"


def _site_hosts() -> set[str]:
    return {request.host.lower(), config.BASE_URL.split("://", 1)[-1].rstrip("/").lower()}


def back_url(default: str = "/") -> str:
    """The page the request came from when it is on this site (path only), else `default`."""
    parts = urlsplit(request.headers.get("Referer", ""))
    if parts.scheme in ("http", "https") and parts.netloc.lower() in _site_hosts():
        if parts.path.startswith("/") and not parts.path.startswith(("//", "/\\")):
            return parts.path + (f"?{parts.query}" if parts.query else "")
    return default


class _SessionInterface(SecureCookieSessionInterface):
    """Session cookie marked Secure only on https requests (the tunnel), so plain-http
    localhost keeps working."""

    def get_cookie_secure(self, app):
        return _is_https(request)


def create_app() -> Flask:
    from housia import sandbox  # not at import time: `python -m housia.sandbox` imports this package

    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.session_interface = _SessionInterface()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    db.init_db()
    sandbox.cleanup_stale()

    from housia.web import (
        applicant,
        applications,
        contract,
        conversations,
        dashboard,
        demo,
        evaluation,
        mock_inbox,
        properties,
        schedule,
        workspace,
    )

    for module in (
        dashboard,
        properties,
        applications,
        evaluation,
        schedule,
        contract,
        applicant,
        conversations,
        mock_inbox,
        demo,
        workspace,
    ):
        app.register_blueprint(module.bp)

    if config.OWNER_PASSWORD and config.SECRET_KEY == "dev":
        raise RuntimeError("Set a strong SECRET_KEY before enabling owner access control.")

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    def _same_origin() -> bool:
        """A public form post must come from this site (the Origin header, when the browser
        sends one, names this host). Blocks other sites from posting with the owner's sign-in."""
        origin = request.headers.get("Origin")
        if not origin:
            return True
        host = origin.split("://", 1)[-1].rstrip("/").lower()
        return host in _site_hosts()

    def signed_in_role() -> str | None:
        """'owner' or 'judge' from this request's Basic credentials, else None.

        Decided on every request from the Authorization header only (nothing is kept in the
        session): username 'owner' needs OWNER_PASSWORD, username 'judge' needs JUDGE_PASSWORD.
        The judge login is off when JUDGE_PASSWORD is empty or equal to OWNER_PASSWORD, and
        whenever OWNER_PASSWORD is not set (then no sign-in exists at all).
        """
        auth = request.authorization
        if not auth or not config.OWNER_PASSWORD:
            return None
        username = (auth.username or "").encode()
        password = (auth.password or "").encode()
        owner_pw = config.OWNER_PASSWORD.encode()
        judge_pw = (config.JUDGE_PASSWORD or "").encode()
        is_owner = secrets.compare_digest(username, b"owner") & secrets.compare_digest(password, owner_pw)
        judge_enabled = bool(judge_pw) and not secrets.compare_digest(judge_pw, owner_pw)
        is_judge = (
            secrets.compare_digest(username, b"judge") & secrets.compare_digest(password, judge_pw)
        ) and judge_enabled
        if is_owner:
            return "owner"
        if is_judge:
            return "judge"
        return None

    def _guest_sandbox_path():
        """The sandbox file for this browser's guest session, or None when it is not a guest.

        A guest session whose sandbox is invalid or gone gets a fresh one (never the main
        database). Raises sandbox.SandboxFull when there is no room for it."""
        if sandbox.SESSION_KEY not in session or not sandbox.guest_enabled(app.secret_key):
            return None
        path = sandbox.path_for(session.get(sandbox.SESSION_KEY))
        if path is None or not path.is_file():
            session[sandbox.SESSION_KEY] = sandbox.create()
            path = sandbox.path_for(session[sandbox.SESSION_KEY])
        sandbox.touch(path)
        return path

    @app.before_request
    def choose_database():
        """First hook of every request: who is asking, and which database file serves them.

        Owner or judge Basic credentials always mean the main database, even with a guest
        session in the same browser. A guest session (and no valid credentials) means that
        guest's sandbox file. Anyone else uses the main database, as before. The choice is
        undone in `clear_database` at the end of the request."""
        g.db_token = db.set_override(None)
        g.viewer_role = signed_in_role()
        if g.viewer_role is not None:
            return None
        try:
            path = _guest_sandbox_path()
        except sandbox.SandboxFull:
            return _demo_full()
        if path is not None:
            db.clear_override(g.pop("db_token"))
            g.db_token = db.set_override(path)
            g.viewer_role = "guest"
        return None

    @app.teardown_request
    def clear_database(_exc):
        db.clear_override(g.pop("db_token", None))

    @app.get("/guest/<code>", endpoint="guest_link")
    def guest_link(code):
        """Private guest demo: a new sandbox for this browser (or its current one), then /guide."""
        expected = (config.GUEST_LINK_CODE or "").encode()
        if not (secrets.compare_digest(code.encode(), expected)
                and sandbox.guest_enabled(app.secret_key)):
            abort(404)
        current = sandbox.path_for(session.get(sandbox.SESSION_KEY))
        if current is None or not current.is_file():
            try:
                session[sandbox.SESSION_KEY] = sandbox.create()
            except sandbox.SandboxFull:
                return _demo_full()
        return redirect("/guide")

    @app.before_request
    def protect_workspace():
        """Owner sign-in (OWNER_PASSWORD) and CSRF check on the owner workspace forms.

        The read-only judge sign-in (JUDGE_PASSWORD) passes wherever the owner sign-in is needed,
        but only for GET/HEAD (plus the mock candidate message); other methods are refused.

        Local requests: sign-in only when OWNER_PASSWORD is set; applicant links and the mock
        portal stay open. Public (tunnelled) requests: only applicant links and static files are
        open; everything else needs the sign-in, and is refused when no password is configured.
        """
        endpoint = request.endpoint or ""
        # A guest has the owner's rights, but only inside their own sandbox database.
        is_guest = g.get("viewer_role") == "guest"
        if is_public_request(request):
            needs_owner = not _public_allowed(endpoint, request.path)
            if needs_owner and not is_guest and not config.OWNER_PASSWORD:
                return Response("Forbidden: owner sign-in is not configured.", 403,
                                {"Content-Type": "text/plain; charset=utf-8"})
            if request.method == "POST" and not _same_origin():
                return Response("Forbidden: cross-site form.", 403,
                                {"Content-Type": "text/plain; charset=utf-8"})
        else:
            # Applicant links (token pages, public apply form) and the mock portal stay reachable.
            needs_owner = not (endpoint in ("workspace.candidate", "static", "guest_link") or endpoint.startswith(
                ("applicant.", "mock_inbox.")
            ))
        if config.OWNER_PASSWORD and needs_owner and not is_guest:
            role = signed_in_role()
            if role is None:
                return Response("Owner sign-in required.", 401,
                                {"WWW-Authenticate": 'Basic realm="HOUSIA owner"'})
            if (role == "judge" and request.method not in ("GET", "HEAD")
                    and endpoint not in JUDGE_ALLOWED_POSTS):
                flash(READ_ONLY_MESSAGE, "error")
                return redirect(back_url(), 303)
        protected_form = endpoint.startswith(("workspace.", "properties.")) or endpoint == "demo.read_all"
        if protected_form and request.method == "POST":
            request.max_content_length = 2_100_000
            expected = session.get("csrf_token")
            if not expected or not secrets.compare_digest(
                expected.encode(), request.form.get("csrf_token", "").encode()
            ):
                abort(400, "This form has expired. Reload the page and try again.")

    @app.after_request
    def private_pages(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
            # "same-origin": other sites never learn our URLs (applicant links hold a token), while
            # our own form posts still carry a real Origin header. With "no-referrer" browsers send
            # "Origin: null" on form posts, which the cross-site check below would refuse.
            response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.before_request
    def run_tick():
        if request.endpoint == "static":
            return None
        from housia.services import scheduling

        with db.tx() as conn:
            scheduling.tick(conn, core.now(conn))
        return None

    @app.errorhandler(core.DomainError)
    def domain_error(error):
        """A rule was broken outside a route's own try block, usually a missing record on a GET page.
        Show the message on the dashboard instead of a 500 page."""
        if request.path == "/":
            return str(error), 500
        flash(str(error), "error")
        return redirect("/")

    @app.template_filter("dt")
    def format_dt(value, fmt="%a %d %b, %H:%M"):
        """Format a datetime or a stored ISO string, e.g. 'Mon 23 Nov, 09:00'."""
        if not value:
            return ""
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        return value.strftime(fmt)

    @app.context_processor
    def common_context():
        with db.tx() as conn:
            unread = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE application_id IS NULL AND is_read = 0"
            ).fetchone()[0]
            return {
                "viewer_role": g.get("viewer_role"),
                "now": core.now(conn),
                "clock_offset_min": int(core.get_setting(conn, "clock_offset_min", "0") or 0),
                "unread_count": unread,
                "nav_properties": conn.execute(
                    "SELECT * FROM properties ORDER BY id"
                ).fetchall(),
                "worker_paused": core.get_setting(conn, "worker_paused", "0") == "1",
            }

    return app
