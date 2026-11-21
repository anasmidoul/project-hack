"""HOUSIA web app factory."""

from datetime import datetime

from flask import Flask, request

from housia import config, core, db


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

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
    ):
        app.register_blueprint(module.bp)

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
