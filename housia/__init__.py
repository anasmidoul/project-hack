"""HOUSIA web app factory."""

import secrets
from datetime import datetime

from flask import Flask, Response, abort, request, session

from housia import config, core, db


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config['SESSION_COOKIE_SECURE'] = config.BASE_URL.startswith('https://')

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

    if config.OWNER_PASSWORD and config.SECRET_KEY == 'dev':
        raise RuntimeError('Set a strong SECRET_KEY before enabling owner access control.')

    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return session['csrf_token']

    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect_workspace():
        endpoint = request.endpoint or ''
        public = endpoint in ('workspace.candidate', 'static')
        if config.OWNER_PASSWORD and not public:
            auth = request.authorization
            if not auth or auth.username != 'owner' or not secrets.compare_digest(
                (auth.password or '').encode(), config.OWNER_PASSWORD.encode()
            ):
                return Response('Owner sign-in required.', 401,
                                {'WWW-Authenticate': 'Basic realm="HOUSIA owner"'})
        protected_form = endpoint.startswith(('workspace.', 'properties.')) or endpoint == 'demo.read_all'
        if protected_form and request.method == 'POST':
            request.max_content_length = 2_100_000
            expected = session.get('csrf_token')
            if not expected or not secrets.compare_digest(expected.encode(), request.form.get('csrf_token', '').encode()):
                abort(400, 'This form has expired. Reload the page and try again.')

    @app.after_request
    def private_pages(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    @app.before_request
    def run_tick():
        if request.endpoint == "static":
            return None
        from housia.services import scheduling

        with db.tx() as conn:
            scheduling.tick(conn, core.now(conn))
        return None

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
