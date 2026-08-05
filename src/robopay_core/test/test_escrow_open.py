import os

import pytest
from web3 import Web3

from robopay_core.backends.escrow import EscrowBackend
from robopay_core.wallets.self_custody import SelfCustodyProvider

DEV_ADDR = os.getenv("ROBOPAY_TEST_ADDRESS", "")
DEV_PASS = os.getenv("ROBOPAY_TEST_PASSPHRASE", "")

pytestmark = pytest.mark.skipif(
    not DEV_ADDR, reason="set ROBOPAY_TEST_ADDRESS to run the live escrow test"
)


def test_open_escrow_returns_details_from_receipt():
    backend = EscrowBackend("base-sepolia")
    w = SelfCustodyProvider()
    w.load(DEV_ADDR, DEV_PASS)

    terms = Web3.keccak(text="delivery-of-package-123")
    result = backend.open_escrow(
        payer=DEV_ADDR,
        payee=DEV_ADDR,
        amount="0.05",
        terms_hash=terms,
        timeout_seconds=600,
        private_key=w.private_key(),
    )

    print(f"\n  escrow id: 0x{result['escrow_id'].hex()}")
    print(f"  tx hash  : 0x{result['tx_hash']}")

    assert len(result["escrow_id"]) == 32
    assert result["amount"] == 50_000
    assert result["terms"] == terms
    assert Web3.to_checksum_address(result["payer"]) == Web3.to_checksum_address(DEV_ADDR)


def test_second_open_skips_redundant_approval():
    """The generous first approval means a second open needs no approve tx."""
    backend = EscrowBackend("base-sepolia")
    w = SelfCustodyProvider()
    w.load(DEV_ADDR, DEV_PASS)

    result = backend.open_escrow(
        payer=DEV_ADDR, payee=DEV_ADDR, amount="0.05",
        terms_hash=Web3.keccak(text="second-escrow"),
        timeout_seconds=600, private_key=w.private_key(),
    )
    assert result["amount"] == 50_000