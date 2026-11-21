"""Private guest demos: each guest browser gets its own copy of the demo database.

A sandbox is one SQLite file `<SANDBOX_DIR>/<id>.db`, copied with SQLite's backup API from the
template (`SANDBOX_TEMPLATE`, built with `python -m housia.sandbox make-template`) or, when there
is no template, from the main database as it is at that moment. The web app selects the file
for a guest's requests with `db.set_override()`; the worker serves recently used sandboxes with
`db.using()`.

Applicant tokens are replaced in every new or reset sandbox, so a link copied out of a sandbox
never opens an applicant in the main database.
"""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import sys
import threading
import time
from pathlib import Path

from housia import config, db

SESSION_KEY = "guest_sandbox"
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{32}")  # secrets.token_urlsafe(24)
ACTIVE_SEC = 60 * 60  # the worker serves sandboxes used in the last hour
EVICT_IDLE_SEC = 30 * 60  # when full, only sandboxes idle this long may be removed
STALE_SEC = 12 * 60 * 60  # removed when the app starts
_SIDE_SUFFIXES = ("", "-wal", "-shm", "-journal")
# Text columns that can hold applicant links (they contain "/<token>").
_LINK_COLUMNS = (("notifications", "title"), ("notifications", "body"),
                 ("messages", "body"), ("mock_messages", "body"))

_lock = threading.Lock()


class SandboxFull(Exception):
    """No room for another sandbox right now."""


def _from_root(name: str) -> Path:
    path = Path(name).expanduser()
    return path if path.is_absolute() else config.ROOT / path


def sandbox_dir() -> Path:
    return _from_root(config.SANDBOX_DIR)


def template_path() -> Path:
    return _from_root(config.SANDBOX_TEMPLATE)


def guest_enabled(signing_key: str | None = None) -> bool:
    """Guest demos need a link code and a non-default secret key (else sessions can be forged)."""
    keys = (config.SECRET_KEY, signing_key if signing_key is not None else config.SECRET_KEY)
    return bool(config.GUEST_LINK_CODE) and all(k and k != "dev" for k in keys)


def is_valid_id(value) -> bool:
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None


def path_for(sandbox_id) -> Path | None:
    """The sandbox file for a valid id, inside the sandbox folder; None for anything else."""
    if not is_valid_id(sandbox_id):
        return None
    folder = sandbox_dir().resolve()
    path = (folder / f"{sandbox_id}.db").resolve()
    return path if path.parent == folder else None


def _files() -> list[tuple[float, Path]]:
    """(mtime, path) of every sandbox file, least recently used first."""
    found = []
    folder = sandbox_dir()
    if not folder.is_dir():
        return found
    for path in folder.glob("*.db"):
        if not is_valid_id(path.stem):
            continue
        try:
            found.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue
    found.sort(key=lambda item: item[0])
    return found


def delete(path: Path) -> None:
    """Remove a sandbox file and SQLite's side files."""
    for suffix in _SIDE_SUFFIXES:
        Path(f"{path}{suffix}").unlink(missing_ok=True)


def touch(path: Path) -> None:
    """Mark a sandbox as used now (writes land in the -wal file, so mtime alone is not enough)."""
    try:
        os.utime(path)
    except OSError:
        pass


def recent(max_age_sec: int = ACTIVE_SEC) -> list[Path]:
    """Sandbox files used in the last `max_age_sec` seconds."""
    cutoff = time.time() - max_age_sec
    return [path for mtime, path in _files() if mtime >= cutoff]


def cleanup_stale(max_age_sec: int = STALE_SEC) -> int:
    """Delete sandboxes (and unfinished copies) not used for `max_age_sec`. Returns the count."""
    cutoff = time.time() - max_age_sec
    removed = 0
    with _lock:
        for mtime, path in _files():
            if mtime < cutoff:
                delete(path)
                removed += 1
        folder = sandbox_dir()
        if folder.is_dir():
            for path in folder.glob("*.db.tmp"):
                try:
                    if path.stat().st_mtime < cutoff:
                        delete(path)
                except FileNotFoundError:
                    pass
    return removed


def _copy(source: Path, dest: Path) -> None:
    """Consistent copy of `source` to `dest` with the backup API (atomic rename at the end)."""
    if not source.is_file():
        raise FileNotFoundError("The sandbox source database does not exist.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    delete(tmp)
    try:
        src = sqlite3.connect(source, timeout=10)
        try:
            out = sqlite3.connect(tmp, timeout=10)
            try:
                src.backup(out)
            finally:
                out.close()
        finally:
            src.close()
        os.replace(tmp, dest)
    finally:
        delete(tmp)


def rotate_tokens(conn) -> None:
    """Give every application a new random token and update the links stored in text."""
    rows = conn.execute("SELECT id, token FROM applications").fetchall()
    # Longest first, so a token that is a prefix of another one is not replaced inside it.
    for app_id, old in sorted(((r[0], r[1]) for r in rows), key=lambda r: -len(r[1])):
        new = secrets.token_urlsafe(24)
        conn.execute("UPDATE applications SET token = ? WHERE id = ?", (new, app_id))
        for table, column in _LINK_COLUMNS:
            conn.execute(
                f"UPDATE {table} SET {column} = replace({column}, ?, ?) WHERE instr({column}, ?) > 0",
                ("/" + old, "/" + new, "/" + old),
            )


def _prepare(path: Path) -> None:
    with db.using(path):
        db.init_db()
        with db.tx() as conn:
            rotate_tokens(conn)


def _make_room() -> None:
    files = _files()
    limit = max(config.SANDBOX_MAX, 0)
    cutoff = time.time() - EVICT_IDLE_SEC
    while len(files) >= limit:
        if not files or files[0][0] > cutoff:
            raise SandboxFull
        delete(files.pop(0)[1])


def create() -> str:
    """Make a new sandbox and return its id. Raises SandboxFull when there is no room."""
    with _lock:
        _make_room()
        sandbox_id = secrets.token_urlsafe(24)
        path = path_for(sandbox_id)
        template = template_path()
        source = template if template.is_file() else db.main_db_path()
        try:
            _copy(source, path)
            _prepare(path)
        except BaseException:
            delete(path)
            raise
    return sandbox_id


def make_template() -> Path:
    """Copy the main database (as it is now) to the sandbox template."""
    with db.using(None):
        db.init_db()
    dest = template_path()
    _copy(db.main_db_path(), dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["make-template"]:
        print("usage: python -m housia.sandbox make-template", file=sys.stderr)
        return 2
    path = make_template()
    print(f"Sandbox template written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
