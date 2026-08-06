from robopay_core.chain_client import ChainClient

from conftest import requires_network

pytestmark = requires_network

EMPTY = "0x000000000000000000000000000000000000dEaD"


def test_native_balance_reads():
    c = ChainClient("base-sepolia")
    bal = c.native_balance(EMPTY)
    assert isinstance(bal, str)
    float(bal)  # parses as a number without error


def test_token_balance_reads():
    c = ChainClient("base-sepolia")
    bal = c.token_balance(EMPTY, "USDC")
    assert isinstance(bal, str)
    float(bal)  # parses cleanly


def test_balances_are_non_negative():
    c = ChainClient("base-sepolia")
    assert float(c.native_balance(EMPTY)) >= 0
    assert float(c.token_balance(EMPTY, "USDC")) >= 0