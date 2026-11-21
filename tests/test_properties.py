import pytest

from housia import core
from housia.services import properties


def _data():
    return {"title": "Test room", "address": "1 Demo Street", "city": "Madrid",
            "rental_type": "residential", "rent_eur": "900", "description": "Bright room",
            "facts": "Near a metro", "required_document": "Payslip", "eval_mode": "assisted",
            "invite_limit": "3", "reply_mode": "assisted", "listing_ref": "demo-test"}


def test_create_and_update_property(conn, t0):
    property_id = properties.create_property(conn, _data(), t0)
    prop = properties.get_property(conn, property_id)
    assert prop["rent_eur"] == 900
    changed = _data() | {"rent_eur": "975", "eval_mode": "automatic"}
    properties.update_property(conn, property_id, changed)
    assert properties.get_property(conn, property_id)["rent_eur"] == 975
    assert properties.get_property(conn, property_id)["eval_mode"] == "automatic"


def test_invalid_property_input_raises_domain_error(conn, t0):
    with pytest.raises(core.DomainError):
        properties.create_property(conn, _data() | {"rental_type": "hotel"}, t0)
