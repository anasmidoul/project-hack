import pytest

GET_ROUTES = [
    "/",
    "/properties/new",
    "/properties/1/edit",
    "/properties/1",
    "/properties/1/applications",
    "/applications/1",
    "/properties/1/evaluation",
    "/properties/1/schedule",
    "/properties/1/contract",
    "/properties/1/conversations",
    "/conversations/1",
    "/inbox",
    "/guide",
    "/apply/1",
    "/a/x",
    "/mock/inbox",
    "/mock/inbox/1",
    "/mock/candidate",
]


def test_app_is_created(client):
    assert client.application is not None
    blueprints = set(client.application.blueprints)
    assert {
        "dashboard", "properties", "applications", "evaluation", "schedule",
        "contract", "applicant", "conversations", "mock_inbox", "demo",
    } <= blueprints


@pytest.mark.parametrize("path", GET_ROUTES)
def test_get_route_responds(client, path):
    """Every page answers. On an empty database a page for one record may be 404 or a redirect
    with a message, never 500."""
    response = client.get(path)
    allowed = (200, 302, 404) if any(ch.isdigit() for ch in path) or path == "/a/x" else (200,)
    assert response.status_code in allowed, f"{path} -> {response.status_code}"


def test_dt_filter(client):
    dt = client.application.jinja_env.filters["dt"]
    assert dt("2026-11-23T09:00:00") == "Mon 23 Nov, 09:00"
    assert dt(None) == ""


def test_old_demo_page_redirects_to_guide(client):
    response = client.get("/demo")
    assert response.status_code == 302 and response.headers["Location"] == "/guide"
    assert client.get("/demo?as=demo-1-01").headers["Location"] == "/guide"


def test_dashboard_has_no_demo_link(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="/demo"' not in html and "Open demo" not in html
    assert 'href="/guide"' in html and "How it works" in html


def test_dashboard_shows_new_logo_and_photos(client):
    client.post("/demo/reset")
    html = client.get("/").get_data(as_text=True)
    assert "housia<span" in html and "M2.586 17.414" in html
    assert '<img class="property-photo" src="/static/photos/' in html


def test_brand_assets_are_served(client):
    for path in ("/static/brand.css", "/static/favicon.svg", "/static/fonts/manrope-latin.woff2",
                 "/static/photos/eixample.jpg", "/static/photos/gracia.jpg", "/static/photos/eixample-bedroom.jpg"):
        assert client.get(path).status_code == 200, path


def test_dashboard_counts_include_portal_conversations(client):
    from housia import db

    client.post("/demo/reset")
    with db.tx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM applications WHERE property_id = 1").fetchone()[0]
        waiting = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE property_id = 1 AND status = 'docs_uploaded'"
        ).fetchone()[0]
        now = "2026-11-23T09:00:00"
        conn.execute("INSERT INTO conversations (property_id, channel, external_id, contact_name, status, created_at) "
                     "VALUES (1, 'mock', 't-99', 'Test Person', 'needs_landlord', ?)", (now,))
    html = client.get("/").get_data(as_text=True)
    assert total > 0
    assert f"{total} enquiries · {waiting + 1} to review" in html
    assert "Imported enquiries" not in html
