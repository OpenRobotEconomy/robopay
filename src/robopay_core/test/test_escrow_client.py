from robopay_core.chain_client import ChainClient
from robopay_core.chains import CHAINS, token_address
from robopay_core.escrow_client import EscrowClient


def _client():
    return EscrowClient(ChainClient("base-sepolia"), "base-sepolia")


def test_connects_to_deployed_escrow():
    c = _client()
    assert c.address == CHAINS["base-sepolia"]["escrow"]
    # the contract exists on-chain (has bytecode)
    assert len(c.w3.eth.get_code(c.address)) > 0


def test_usdc_is_allowed():
    c = _client()
    usdc = token_address("base-sepolia", "USDC")
    assert c.is_token_allowed(usdc) is True


def test_random_token_is_not_allowed():
    c = _client()
    assert c.is_token_allowed("0x000000000000000000000000000000000000dEaD") is False


def test_unknown_escrow_reads_as_none():
    c = _client()
    ghost = bytes(32)
    e = c.get_escrow(ghost)
    assert e["state"] == "none"
    assert e["amount"] == 0