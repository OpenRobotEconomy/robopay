from robopay_core.backends.mock import MockBackend


def test_transfer_moves_funds():
    b = MockBackend()
    b.fund("0xalice", 10, "USDC")
    r = b.transfer("0xalice", "0xbob", "4", "USDC")
    assert r["success"]
    assert b.balance("0xalice")["USDC"] == 6
    assert b.balance("0xbob")["USDC"] == 4


def test_insufficient_funds_is_rejected():
    b = MockBackend()
    b.fund("0xalice", 1, "USDC")
    r = b.transfer("0xalice", "0xbob", "5", "USDC")
    assert not r["success"]
    assert r["error"] == "insufficient_funds"
