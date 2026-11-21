"""SQLite access: connections, transactions, schema creation and demo reset."""

import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar, Token
from pathlib import Path

from housia import config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
WORKSPACE_SCHEMA = SCHEMA_PATH.with_name("workspace.sql")

# Optional database file for the current request or worker pass (a guest sandbox). None means
# the main database. Set it with `using()` or `set_override()`/`clear_override()`.
_override: ContextVar[Path | None] = ContextVar("housia_db_override", default=None)


def main_db_path() -> Path:
    """Path of the main database file. A relative HOUSIA_DB is taken from the repo root."""
    path = Path(config.HOUSIA_DB)
    if not path.is_absolute():
        path = config.ROOT / path
    return path


def db_path() -> Path:
    """Path of the database file in use: the override when one is set, else the main one."""
    override = _override.get()
    return override if override is not None else main_db_path()


def set_override(path: Path | None) -> Token:
    """Use `path` (None = main database) until `clear_override(token)`."""
    return _override.set(Path(path) if path is not None else None)


def clear_override(token: Token | None) -> None:
    """Undo `set_override`. Always leaves the main database selected if the token is unusable."""
    try:
        if token is not None:
            _override.reset(token)
            return
    except ValueError:  # token from another context
        pass
    _override.set(None)


@contextmanager
def using(path: Path | None):
    """Run the block with `path` as the database (for code outside a request)."""
    token = set_override(path)
    try:
        yield
    finally:
        clear_override(token)


def get_conn() -> sqlite3.Connection:
    """New connection with Row factory and foreign keys on.

    The connection is in autocommit mode; use `tx()` for transactions.
    """
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")  # web app and worker share the file
    return conn


@contextmanager
def tx():
    """BEGIN IMMEDIATE ... COMMIT, or ROLLBACK on any exception. Always closes the connection."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
    finally:
        conn.close()


def apply_schema(conn: sqlite3.Connection) -> None:
    """Run schema.sql on a connection that has no tables yet."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.executescript(WORKSPACE_SCHEMA.read_text(encoding="utf-8"))


def init_db() -> None:
    """Create the tables if they are missing."""
    conn = get_conn()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'properties'"
        ).fetchone()
        if not exists:
            apply_schema(conn)
        else:
            conn.executescript(WORKSPACE_SCHEMA.read_text(encoding="utf-8"))
    finally:
        conn.close()


def reset_db() -> None:
    """Drop every table, create the schema again and load the seed data."""
    from housia import core, demo_extra, seed  # lazy: seed imports services

    conn = get_conn()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        conn.execute("BEGIN IMMEDIATE")
        for name in names:
            conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        conn.execute("COMMIT")
        apply_schema(conn)
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()

    with tx() as conn:
        seed.run(conn, core.now(conn))
        demo_extra.load(conn, core.now(conn))
        if _override.get() is not None:
            # A guest sandbox: the seed's fixed tokens would also open the main database's
            # applicants, so this copy gets its own.
            from housia import sandbox

            sandbox.rotate_tokens(conn)
