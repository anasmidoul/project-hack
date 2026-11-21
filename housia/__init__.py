"""HOUSIA web app factory."""

import secrets
from datetime import datetime

from flask import Flask, Response, abort, flash, redirect, request, session
from flask.sessions import SecureCookieSessionInterface

from housia import config, core, db

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
        endpoint in ("workspace.candidate", "static")
        or endpoint.startswith("applicant.")
        or path == "/favicon.ico"
    )


def _is_https(req) -> bool:
    if req.is_secure:
        return True
    return is_public_request(req) and req.headers.get("X-Forwarded-Proto", "").lower() == "https"


class _SessionInterface(SecureCookieSessionInterface):
    """Session cookie marked Secure only on https requests (the tunnel), so plain-http
    localhost keeps working."""

    def get_cookie_secure(self, app):
        return _is_https(request)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.session_interface = _SessionInterface()
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    db.init_db()

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
        allowed = {request.host.lower(), config.BASE_URL.split("://", 1)[-1].rstrip("/").lower()}
        return host in allowed

    def owner_signed_in() -> bool:
        auth = request.authorization
        return bool(auth) and secrets.compare_digest(
            (auth.username or "").encode(), b"owner"
        ) & secrets.compare_digest(
            (auth.password or "").encode(), config.OWNER_PASSWORD.encode()
        )

    @app.before_request
    def protect_workspace():
        """Owner sign-in (OWNER_PASSWORD) and CSRF check on the owner workspace forms.

        Local requests: sign-in only when OWNER_PASSWORD is set; applicant links and the mock
        portal stay open. Public (tunnelled) requests: only applicant links and static files are
        open; everything else needs the sign-in, and is refused when no password is configured.
        """
        endpoint = request.endpoint or ""
        if is_public_request(request):
            needs_owner = not _public_allowed(endpoint, request.path)
            if needs_owner and not config.OWNER_PASSWORD:
                return Response("Forbidden: owner sign-in is not configured.", 403,
                                {"Content-Type": "text/plain; charset=utf-8"})
            if request.method == "POST" and not _same_origin():
                return Response("Forbidden: cross-site form.", 403,
                                {"Content-Type": "text/plain; charset=utf-8"})
        else:
            # Applicant links (token pages, public apply form) and the mock portal stay reachable.
            needs_owner = not (endpoint in ("workspace.candidate", "static") or endpoint.startswith(
                ("applicant.", "mock_inbox.")
            ))
        if config.OWNER_PASSWORD and needs_owner and not owner_signed_in():
            return Response("Owner sign-in required.", 401,
                            {"WWW-Authenticate": 'Basic realm="HOUSIA owner"'})
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
            response.headers["Referrer-Policy"] = "no-referrer"
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
                "now": core.now(conn),
                "clock_offset_min": int(core.get_setting(conn, "clock_offset_min", "0") or 0),
                "unread_count": unread,
                "nav_properties": conn.execute(
                    "SELECT * FROM properties ORDER BY id"
                ).fetchall(),
                "worker_paused": core.get_setting(conn, "worker_paused", "0") == "1",
            }

    return app
