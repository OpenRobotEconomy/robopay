import pytest

from robopay_core.chain_client import ChainClient


def test_connects():
    c = ChainClient("base-sepolia")
    assert c.is_connected()


def test_reports_correct_chain_id():
    c = ChainClient("base-sepolia")
    assert c.chain_id() == 84532


def test_block_number_advances():
    c = ChainClient("base-sepolia")
    n = c.block_number()
    assert n > 0

def test_falls_back_to_public_when_env_empty(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "")
    c = ChainClient("base-sepolia")
    assert c.using_public_rpc is True
    assert c.is_connected()


def test_falls_back_to_public_when_env_whitespace(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "   ")
    c = ChainClient("base-sepolia")
    assert c.using_public_rpc is True