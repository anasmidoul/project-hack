"""SQLite access: connections, transactions, schema creation and demo reset."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from housia import config

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
WORKSPACE_SCHEMA = SCHEMA_PATH.with_name("workspace.sql")


def db_path() -> Path:
    """Path of the database file. A relative HOUSIA_DB is taken from the repo root."""
    path = Path(config.HOUSIA_DB)
    if not path.is_absolute():
        path = config.ROOT / path
    return path


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
    from housia import core, seed  # lazy: seed imports services

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
