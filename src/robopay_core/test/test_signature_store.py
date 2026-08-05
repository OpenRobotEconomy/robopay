import pytest

from robopay_core.signature_store import SignatureStore

EID = b"\x01" * 32


def test_collects_both_roles():
    s = SignatureStore()
    assert not s.has_both(EID)
    s.add(EID, "payer", b"sig-p")
    assert not s.has_both(EID)
    s.add(EID, "payee", b"sig-e")
    assert s.has_both(EID)
    assert s.get(EID) == {"payer": b"sig-p", "payee": b"sig-e"}


def test_signature_arriving_early_is_kept():
    s = SignatureStore()
    s.add(EID, "payee", b"early")
    assert s.get(EID)["payee"] == b"early"


def test_rejects_bad_role():
    s = SignatureStore()
    with pytest.raises(ValueError):
        s.add(EID, "stranger", b"sig")


def test_clear_removes_entry():
    s = SignatureStore()
    s.add(EID, "payer", b"x")
    s.clear(EID)
    assert s.get(EID) == {}