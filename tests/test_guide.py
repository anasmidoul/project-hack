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


def test_old_demo_page_redirects_to_guide(client):
    client.post("/demo/reset")
    response = client.get("/demo")
    assert response.status_code == 302 and response.headers["Location"] == "/guide"


def test_guide_starts_with_start_here_and_has_no_demo_room(client):
    client.post("/demo/reset")
    html = client.get("/guide").get_data(as_text=True)
    assert 'class="guide-start"' in html and "Start here" in html
    assert html.index('class="guide-start"') < html.index('class="guide-step"')
    assert "This is your own copy of the demo" not in html  # only for a guest
    assert 'href="/demo"' not in html
    for gone in ("demo room", "Demo room", "Applicant preview", "View applicant", "phone frame"):
        assert gone not in html, gone


def test_guide_has_demo_tools(client):
    client.post("/demo/reset")
    html = client.get("/guide").get_data(as_text=True)
    assert 'id="tools"' in html and "Demo tools" in html and "Demo time:" in html
    assert html.count('action="/demo/clock#tools"') == 2
    assert '<input type="hidden" name="minutes" value="10">' in html
    assert '<input type="hidden" name="minutes" value="30">' in html
    assert html.count('action="/demo/reset#tools"') == 1 and "Reset demo" in html
    # Between the waiting-list step and the features; steps 7 and 9 point to it.
    assert html.index('id="step-9"') < html.index('id="tools"') < html.index('id="features"')
    assert html.count('href="#tools"') >= 3


def test_clock_post_from_guide_returns_to_guide(client):
    from housia import db

    client.post("/demo/reset")
    response = client.post("/demo/clock", data={"minutes": "30"},
                           headers={"Referer": "http://localhost/guide"})
    assert response.status_code == 302 and response.headers["Location"] == "/guide"
    with db.tx() as conn:
        assert conn.execute("SELECT value FROM settings WHERE key='clock_offset_min'").fetchone()[0] == "30"
    html = client.get("/guide").get_data(as_text=True)
    assert "30 minutes from real time" in html
    response = client.post("/demo/reset", headers={"Referer": "http://localhost/guide"})
    assert response.status_code == 302 and response.headers["Location"] == "/guide"
    assert "0 minutes from real time" in client.get("/guide").get_data(as_text=True)


def test_demo_tools_never_redirect_to_another_site(client):
    for headers in ({}, {"Referer": "https://evil.example/guide"}, {"Referer": "http://localhost//evil.example/x"},
                    {"Referer": "javascript:alert(1)"}):
        for path, data in [("/demo/clock", {"minutes": "10"}), ("/demo/reset", {}), ("/inbox/read-all", {})]:
            if path == "/inbox/read-all":
                client.get("/inbox")  # sets the CSRF token in the session
                with client.session_transaction() as s:
                    data = {"csrf_token": s["csrf_token"]}
            response = client.post(path, data=data, headers=headers)
            assert response.status_code == 302 and response.headers["Location"] == "/guide", (path, headers)
    # From a page of this site: back to that page, query included.
    response = client.post("/demo/clock", data={"minutes": "10"},
                           headers={"Referer": "http://localhost/properties/2/schedule?x=1"})
    assert response.headers["Location"] == "/properties/2/schedule?x=1"


def test_dashboard_links_to_guide(client):
    client.post("/demo/reset")
    html = client.get("/").get_data(as_text=True)
    assert 'href="/guide"' in html and "How it works" in html
    assert 'href="/demo"' not in html and "Open demo" not in html


def test_application_page_links_to_applicant_page(client):
    from housia import db

    client.post("/demo/reset")
    with db.tx() as conn:
        app_id, token = conn.execute("SELECT id, token FROM applications ORDER BY id LIMIT 1").fetchone()
    html = client.get(f"/applications/{app_id}").get_data(as_text=True)
    assert f'<a class="button button--secondary" href="/a/{token}" target="_blank" rel="noopener">Open their applicant page' in html


def test_applicant_page_back_to_guide_only_for_explorers(client, monkeypatch):
    from housia import config, db

    client.post("/demo/reset")
    with db.tx() as conn:
        token = conn.execute("SELECT token FROM applications ORDER BY id LIMIT 1").fetchone()[0]
    public = {"Cf-Connecting-Ip": "203.0.113.5", "X-Forwarded-Proto": "https"}
    monkeypatch.setattr(config, "OWNER_PASSWORD", "owner-pass-for-test")
    monkeypatch.setattr(config, "JUDGE_PASSWORD", "judge-pass-for-test")
    # A real candidate: no sign-in, no guest session.
    page = client.get(f"/a/{token}", headers=public)
    assert page.status_code == 200 and "Back to the guide" not in page.get_data(as_text=True)
    for auth in [("owner", "owner-pass-for-test"), ("judge", "judge-pass-for-test")]:
        html = client.get(f"/a/{token}", headers=public, auth=auth).get_data(as_text=True)
        assert '<a href="/guide" style="color:#005db8">← Back to the guide</a>' in html, auth
    # A guest, in their own copy.
    monkeypatch.setattr(config, "GUEST_LINK_CODE", "guide-test-code")
    guest = client.application.test_client()
    assert guest.get("/guest/guide-test-code", headers=public).headers["Location"] == "/guide"
    assert guest.get("/guide", headers=public).status_code == 200
    from housia import sandbox

    with guest.session_transaction() as s:
        path = sandbox.path_for(s[sandbox.SESSION_KEY])
    with db.using(path), db.tx() as conn:
        guest_token = conn.execute("SELECT token FROM applications ORDER BY id LIMIT 1").fetchone()[0]
    html = guest.get(f"/a/{guest_token}", headers=public).get_data(as_text=True)
    assert "Back to the guide" in html


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
