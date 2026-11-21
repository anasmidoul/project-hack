"""Unit A7 tests.

Must prove:
- a text with a name, email, phone, DNI, NIE and IBAN comes out with none of them
- unmask(mask(x)) returns x
- the same value gets the same placeholder
- assert_clean raises when a known value survives
"""
import pytest

from housia import privacy

KNOWN = {"NAME": "Lucía Fernández Ruiz", "EMAIL": "lucia.f@example.com", "PHONE": "600 000 001"}

TEXT = (
    "Hola, soy Lucia FERNANDEZ ruiz, email lucia.f@example.com, móvil +34 600 000 001.\n"
    "Full name: Lucía Fernández Ruiz\n"
    "DNI: 12345678Z\n"
    "Also NIE X1234567L and IBAN ES91 2100 0418 4502 0005 1332. Fernández will pay.\n"
)

SECRETS = [
    "Lucía", "Lucia", "Fernández", "FERNANDEZ", "Ruiz", "lucia.f@example.com",
    "600 000 001", "12345678Z", "X1234567L", "ES91 2100 0418 4502 0005 1332",
]


def test_mask_removes_name_contact_and_ids():
    masked = privacy.mask(TEXT, KNOWN)
    for secret in SECRETS:
        assert secret.lower() not in masked.text.lower()
    assert "[NAME_1]" in masked.text
    assert "[EMAIL_1]" in masked.text
    assert "[PHONE_1]" in masked.text
    assert "[ID_1]" in masked.text and "[ID_2]" in masked.text
    assert "[IBAN_1]" in masked.text
    privacy.assert_clean(masked.text, masked.mapping)


def test_unmask_restores_original():
    text = "Ana Pérez (ana@example.com, 612 345 678), DNI 87654321X. Ana confirms."
    masked = privacy.mask(text, {"NAME": "Ana Pérez"})
    assert masked.text != text
    assert privacy.unmask(masked.text, masked.mapping) == text


def test_same_value_same_placeholder():
    text = "Name: Ana Pérez\nPayslip holder: ANA PEREZ. Contact ana@example.com or ana@example.com."
    masked = privacy.mask(text, {"NAME": "Ana Pérez"})
    names = [ph for ph in masked.mapping if ph.startswith("[NAME_")]
    assert names == ["[NAME_1]"]
    assert masked.text.count("[NAME_1]") == 2
    assert masked.text.count("[EMAIL_1]") == 2
    assert "[EMAIL_2]" not in masked.text


def test_assert_clean_raises_when_value_survives():
    mapping = {"[NAME_1]": "Ana Pérez"}
    with pytest.raises(privacy.PrivacyError) as exc:
        privacy.assert_clean("Hello ANA PEREZ", mapping)
    assert "Ana" not in str(exc.value)
    privacy.assert_clean("Hello [NAME_1]", mapping)
