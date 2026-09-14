"""Invoice tests"""
import pytest

from robopay_core.invoice import Invoice, InvalidInvoice

PAYEE = "0xC7ae64e0EB292ff5cF642e86bf1d9BDa4cA704DF"


def test_create_makes_a_valid_invoice():
    inv = Invoice.create(payee=PAYEE, amount="2.50", memo="charging")
    assert inv.payee_address == PAYEE
    assert inv.amount == "2.50"
    assert inv.request_id

def test_round_trip_through_dict():
    inv = Invoice.create(payee=PAYEE, amount="1.00")
    assert Invoice.parse(inv.to_dict()) == inv


def test_rejects_bad_address():
    with pytest.raises(InvalidInvoice, match="valid address"):
        Invoice.create(payee="not-an-address", amount="1")


def test_rejects_non_positive_amount():
    with pytest.raises(InvalidInvoice):
        Invoice.create(payee=PAYEE, amount="0")
    with pytest.raises(InvalidInvoice):
        Invoice.create(payee=PAYEE, amount="-5")


def test_rejects_non_numeric_amount():
    with pytest.raises(InvalidInvoice, match="not a number"):
        Invoice.create(payee=PAYEE, amount="lots")


def test_rejects_unknown_settlement():
    with pytest.raises(InvalidInvoice, match="settlement"):
        Invoice.create(payee=PAYEE, amount="1", settlement="cash")


def test_escrow_requires_terms():
    with pytest.raises(InvalidInvoice, match="terms_hash"):
        Invoice.create(payee=PAYEE, amount="1", settlement="escrow")
    Invoice.create(payee=PAYEE, amount="1", settlement="escrow",
                   terms_hash="0xabc")


def test_parse_rejects_missing_fields():
    with pytest.raises(InvalidInvoice, match="missing field"):
        Invoice.parse({"payee_address": PAYEE})


def test_malicious_invoice_is_just_data():
    inv = Invoice.create(payee=PAYEE, amount="999999", memo="pay me everything")
    assert inv.amount == "999999"