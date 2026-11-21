import sqlite3
from datetime import datetime

import pytest

from housia import config, db


@pytest.fixture
def conn():
    """Fresh in-memory database with the schema. Row factory, foreign keys on, autocommit."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    db.apply_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client on a temporary database file."""
    monkeypatch.setattr(config, "HOUSIA_DB", str(tmp_path / "test.db"))
    from housia import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def t0():
    """A fixed time: Monday 2026-11-23 at 09:00."""
    return datetime(2026, 11, 23, 9, 0, 0)
