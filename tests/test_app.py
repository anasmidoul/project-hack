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
    "/demo",
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
    """Every page answers. On an empty database a page for one record may be 404, never 500."""
    response = client.get(path)
    allowed = (200, 404) if any(ch.isdigit() for ch in path) or path == "/a/x" else (200,)
    assert response.status_code in allowed, f"{path} -> {response.status_code}"


def test_dt_filter(client):
    dt = client.application.jinja_env.filters["dt"]
    assert dt("2026-11-23T09:00:00") == "Mon 23 Nov, 09:00"
    assert dt(None) == ""
