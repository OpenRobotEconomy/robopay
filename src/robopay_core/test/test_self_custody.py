from robopay_core.wallets.self_custody import SelfCustodyProvider


def test_create_returns_valid_address():
    w = SelfCustodyProvider()
    addr = w.create()
    assert addr.startswith("0x")
    assert len(addr) == 42


def test_address_matches_after_create():
    w = SelfCustodyProvider()
    addr = w.create()
    assert w.address() == addr


def test_two_wallets_are_different():
    a = SelfCustodyProvider().create()
    b = SelfCustodyProvider().create()
    assert a != b


def test_private_key_available_but_distinct_from_address():
    w = SelfCustodyProvider()
    addr = w.create()
    pk = w.private_key()
    assert pk.startswith("0x")
    assert len(pk) == 66
    assert pk != addr


def test_no_wallet_raises():
    w = SelfCustodyProvider()
    assert w.address() == ""
    try:
        w.private_key()
        assert False, "should have raised"
    except RuntimeError:
        pass