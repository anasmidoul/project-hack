"""Route unit B4: schedule blueprint (stub).

Contract: DESIGN.md section 9.
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, abort, flash, redirect, render_template, request

from housia import core, db
from housia.services import properties, scheduling

bp = Blueprint("schedule", __name__)


@bp.get("/properties/<int:property_id>/schedule")
def page(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            slots = scheduling.list_slots(conn, property_id)
    except core.DomainError as exc:
        flash(str(exc), "error")
        return redirect("/")
    return render_template(
        "schedule.html",
        property=prop,
        slots=slots,
    )


@bp.post("/properties/<int:property_id>/slots")
def create_slot(property_id):
    try:
        starts_at = datetime.strptime(f"{request.form['date']} {request.form['time']}", "%Y-%m-%d %H:%M")
        duration = int(request.form.get("duration_min", "30"))
        with db.tx() as conn:
            scheduling.create_slot(conn, property_id, starts_at, duration, core.now(conn))
        flash("Viewing slot created.", "ok")
    except (core.DomainError, KeyError, ValueError) as exc:
        flash(str(exc) if isinstance(exc, core.DomainError) else "Enter a valid date, time and duration.", "error")
    return redirect(f"/properties/{property_id}/schedule")


@bp.post("/slots/<int:slot_id>/delete")
def delete_slot(slot_id):
    try:
        with db.tx() as conn:
            slot = conn.execute("SELECT property_id FROM slots WHERE id=?", (slot_id,)).fetchone()
            if slot is None:
                raise core.DomainError("Viewing slot not found.")
            property_id = slot["property_id"]
            scheduling.delete_slot(conn, slot_id)
        flash("Viewing slot deleted.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
        if "property_id" not in locals():
            return redirect("/")
    return redirect(f"/properties/{property_id}/schedule")


@bp.post("/slots/<int:slot_id>/cancel")
def cancel_slot(slot_id):
    try:
        with db.tx() as conn:
            slot = conn.execute("SELECT property_id FROM slots WHERE id=?", (slot_id,)).fetchone()
            if slot is None:
                raise core.DomainError("Viewing slot not found.")
            property_id = slot["property_id"]
            scheduling.cancel_booking(conn, slot_id, "landlord", core.now(conn))
        flash("Viewing cancelled.", "ok")
    except core.DomainError as exc:
        flash(str(exc), "error")
        if "property_id" not in locals():
            return redirect("/")
    return redirect(f"/properties/{property_id}/schedule")


def _ics_text(value):
    value = str(value if value is not None else "")
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def _ics_fold(line):
    """Fold to at most 75 bytes per line, never splitting a UTF-8 character."""
    out, current, size, limit = [], "", 0, 75
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            out.append(current)
            current, size, limit = " ", 1, 75
        current += char
        size += width
    out.append(current)
    return "\r\n".join(out)


@bp.get("/properties/<int:property_id>/schedule.ics")
def calendar_file(property_id):
    try:
        with db.tx() as conn:
            prop = properties.get_property(conn, property_id)
            slots = scheduling.list_slots(conn, property_id)
    except core.DomainError:
        abort(404)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    title = prop["title"]
    location = ", ".join(part for part in (prop["address"], prop["city"]) if part)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HOUSIA//Viewings//EN", "CALSCALE:GREGORIAN"]
    for slot in slots:
        start = datetime.fromisoformat(slot["starts_at"])
        end = start + timedelta(minutes=slot["duration_min"])
        waiting = len(slot["waitlist"])
        if slot["booked"]:
            name = slot["booked"]["name"]
            summary = f"Viewing: {title} \u2014 {name}"
            description = f"Applicant: {name}. People on the waiting list: {waiting}."
        elif slot["offer"]:
            summary = f"Viewing slot (offered): {title}"
            description = ""
        else:
            summary = f"Viewing slot (free): {title}"
            description = ""
        lines += ["BEGIN:VEVENT", f"UID:slot-{slot['id']}@housia", f"DTSTAMP:{stamp}",
                  f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}", f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                  f"SUMMARY:{_ics_text(summary)}", f"LOCATION:{_ics_text(location)}"]
        if description:
            lines.append(f"DESCRIPTION:{_ics_text(description)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    body = "".join(_ics_fold(line) + "\r\n" for line in lines)
    return Response(body, content_type="text/calendar; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="viewings-property-{property_id}.ics"'})
