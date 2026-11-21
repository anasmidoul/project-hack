import re

import pytest

HINT_PAGES = [
    "/properties/1",
    "/properties/1/applications",
    "/applications/1",
    "/properties/1/evaluation",
    "/properties/1/schedule",
    "/properties/1/contract",
    "/properties/1/conversations",
]


def _links(html):
    return sorted(set(re.findall(r'href="(/[^"#]*)', html)))


def test_guide_shows_walkthrough_and_features(client):
    client.post("/demo/reset")
    response = client.get("/guide")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Try it in five minutes" in html and html.count('class="guide-step"') == 9
    assert "What HOUSIA does" in html and html.count('class="card guide-feature"') == 8
    assert "What is real in this demo" in html and "Portalia" in html
    # Built from the seeded data: the waiting-list scenario and a candidate's personal link.
    assert "Gabi Soler" in html and "Hugo Vidal" in html and "Inés Ferrer" in html
    assert 'href="/a/demo-1-01"' in html and 'href="/mock/candidate"' in html


def test_every_internal_guide_link_works(client):
    client.post("/demo/reset")
    links = _links(client.get("/guide").get_data(as_text=True))
    assert "/properties/2/schedule" in links
    for path in links:
        assert client.get(path).status_code == 200, path


def test_guide_falls_back_to_dashboard_without_data(client):
    from housia import db

    with db.tx() as conn:
        for table in ("waitlist", "slots", "notifications", "messages", "conversations", "applications"):
            conn.execute(f"DELETE FROM {table}")
    response = client.get("/guide")
    assert response.status_code == 200
    for path in _links(response.get_data(as_text=True)):
        assert client.get(path).status_code == 200, path


def test_demo_page_keeps_frames_and_links_to_guide(client):
    client.post("/demo/reset")
    html = client.get("/demo").get_data(as_text=True)
    assert 'class="rental-animation"' in html and "rental_animation.css" in html
    assert 'title="Landlord workspace"' in html and 'title="Applicant experience"' in html
    assert 'class="guide-start"' in html and 'href="/guide"' in html
    assert html.index('class="guide-start"') < html.index('title="Landlord workspace"')


def test_dashboard_links_to_guide(client):
    client.post("/demo/reset")
    html = client.get("/").get_data(as_text=True)
    assert 'href="/guide"' in html and "How it works" in html
    assert 'href="/demo"' in html


@pytest.mark.parametrize("path", HINT_PAGES + ["conversation"])
def test_landlord_pages_show_hint(client, path):
    client.post("/demo/reset")
    if path == "conversation":
        from housia import db

        with db.tx() as conn:
            conv = conn.execute(
                "INSERT INTO conversations (property_id, channel, external_id, contact_name, status, created_at) "
                "VALUES (1, 'mock', 't-guide', 'Test Person', 'open', '2026-11-23T09:00:00') RETURNING id"
            ).fetchone()
        path = f"/conversations/{conv['id']}"
    html = client.get(path).get_data(as_text=True)
    assert html.count('class="page-hint"') == 1, path
    assert 'href="/guide#' in html and "/static/guide.css" in html
