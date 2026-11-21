import re


def test_configure_screening_link_opens_the_brief_form(client):
    client.post("/demo/reset")
    html = client.get("/properties/1/applications").get_data(as_text=True)
    m = re.search(r'<a [^>]*href="([^"]+)"[^>]*>Configure screening</a>', html)
    assert m, "Configure screening link missing"
    page = client.get(m.group(1).replace("&amp;", "&"))
    assert page.status_code == 200
    assert 'name="min_net_eur"' in page.get_data(as_text=True)
