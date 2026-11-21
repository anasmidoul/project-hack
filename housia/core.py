"""Shared helpers used by every service: errors, clock, settings, notifications, statuses."""

from datetime import datetime, timedelta

from housia import config


class DomainError(Exception):
    """A business rule was broken. str(e) is shown to the user."""


APPLICATION_STATUSES = (
    "new",
    "docs_requested",
    "docs_uploaded",
    "docs_correction",
    "docs_approved",
    "invited",
    "booked",
    "attended",
    "absent",
    "finalist",
    "completed",
    "closed",
)

TIME_BANDS = ("morning", "afternoon", "weekend")

INVITABLE_STATUSES = ("docs_uploaded", "docs_approved")
INVITED_BY_VALUES = ("landlord", "auto")


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return str(value)


def now(conn) -> datetime:
    """Real local time plus the demo clock offset (setting clock_offset_min), to the second."""
    offset = int(get_setting(conn, "clock_offset_min", "0") or 0)
    return datetime.now().replace(microsecond=0) + timedelta(minutes=offset)


def get_setting(conn, key, default=None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else default


def set_setting(conn, key, value) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def notify(conn, *, property_id, application_id, title, body, now) -> None:
    """Store a notification. application_id=None means it is for the landlord."""
    conn.execute(
        "INSERT INTO notifications (property_id, application_id, title, body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (property_id, application_id, title, body or "", _iso(now)),
    )


def _get_application(conn, application_id):
    row = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if row is None:
        raise DomainError("Application not found.")
    return row


def set_status(conn, application_id, status) -> None:
    """Set an application's status. Checks the value, not the transition (callers own that)."""
    if status not in APPLICATION_STATUSES:
        raise DomainError(f"Unknown application status: {status}.")
    _get_application(conn, application_id)
    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (status, application_id))


def invited_count(conn, property_id) -> int:
    """Number of applications of the property with calendar access."""
    row = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE property_id = ? AND calendar_access = 1",
        (property_id,),
    ).fetchone()
    return row[0]


def grant_calendar_access(conn, application_id, invited_by, now) -> None:
    """Give an applicant access to the viewing calendar (status -> invited)."""
    if invited_by not in INVITED_BY_VALUES:
        raise DomainError(f"Unknown inviter: {invited_by}.")
    app = _get_application(conn, application_id)
    if app["status"] not in INVITABLE_STATUSES:
        raise DomainError(
            "Calendar access can only be given after the document has been uploaded or approved."
        )
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (app["property_id"],)
    ).fetchone()
    if prop is None:
        raise DomainError("Property not found.")
    if invited_count(conn, prop["id"]) >= prop["invite_limit"]:
        raise DomainError(
            f"The invite limit of {prop['invite_limit']} for this property has been reached."
        )
    conn.execute(
        "UPDATE applications SET calendar_access = 1, invited_by = ?, status = 'invited' "
        "WHERE id = ?",
        (invited_by, application_id),
    )
    notify(
        conn,
        property_id=prop["id"],
        application_id=application_id,
        title="You can now book a viewing",
        body=f"Choose a viewing time for {prop['title']}: {applicant_url(app['token'])}",
        now=now,
    )


def time_band(dt) -> str:
    """'weekend' on Saturday or Sunday, else 'morning' before 14:00, else 'afternoon'.

    Accepts a datetime or an ISO string.
    """
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.weekday() >= 5:
        return "weekend"
    return "morning" if dt.hour < 14 else "afternoon"


def applicant_url(token) -> str:
    return f"{config.BASE_URL.rstrip('/')}/a/{token}"
