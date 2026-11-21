import pytest

from housia import core, seed
from housia.services import evaluation


def _app_ids(conn, property_id):
    return [row["id"] for row in conn.execute(
        "SELECT id FROM applications WHERE property_id=? AND status='docs_approved' ORDER BY created_at,id",
        (property_id,),
    )]


def test_rank_scores_and_tie_breaks_by_submission_time(conn, t0):
    seed.run(conn, t0)
    ranked = evaluation.rank(conn, 1, t0)
    # Third applicant is available at weekends and one free slot is on a Saturday.
    assert [item.score for item in ranked] == [2, 2, 1]
    assert ranked[0].name == "Dani López"
    assert ranked[1].name == "Eva Torres"
    assert ranked[0].position == 1


def test_assisted_evaluation_does_not_invite(conn, t0):
    seed.run(conn, t0)
    before = conn.execute("SELECT id,status,calendar_access FROM applications WHERE property_id=1").fetchall()
    result = evaluation.evaluate(conn, 1, t0)
    after = conn.execute("SELECT id,status,calendar_access FROM applications WHERE property_id=1").fetchall()
    assert result.mode == "assisted"
    assert result.invited_ids == []
    assert [tuple(row) for row in before] == [tuple(row) for row in after]


def test_automatic_evaluation_stops_at_remaining_limit(conn, t0):
    seed.run(conn, t0)
    result = evaluation.evaluate(conn, 2, t0)
    assert result.mode == "automatic"
    assert result.remaining == 2
    assert len(result.invited_ids) == 2
    assert len(result.left_out_ids) == 2
    assert core.invited_count(conn, 2) == 5


def test_assisted_invite_rejects_selection_over_limit(conn, t0):
    seed.run(conn, t0)
    ids = _app_ids(conn, 1)
    conn.execute("UPDATE properties SET invite_limit=1 WHERE id=1")
    with pytest.raises(core.DomainError):
        evaluation.invite(conn, 1, ids[:2], t0)
