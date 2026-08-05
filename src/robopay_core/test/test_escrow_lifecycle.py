import os
import time

import pytest
from web3 import Web3

from robopay_core.backends.escrow import EscrowBackend
from robopay_core.wallets.self_custody import SelfCustodyProvider

DEV_ADDR = os.getenv("ROBOPAY_TEST_ADDRESS", "")
DEV_PASS = os.getenv("ROBOPAY_TEST_PASSPHRASE", "")

pytestmark = pytest.mark.skipif(
    not DEV_ADDR, reason="set ROBOPAY_TEST_ADDRESS to run the live lifecycle test"
)


@pytest.fixture(scope="module")
def setup():
    backend = EscrowBackend("base-sepolia")
    w = SelfCustodyProvider()
    w.load(DEV_ADDR, DEV_PASS)
    return backend, w.private_key()


def test_open_sign_and_release(setup):
    backend, pk = setup

    opened = backend.open_escrow(
        payer=DEV_ADDR, payee=DEV_ADDR, amount="0.05",
        terms_hash=Web3.keccak(text="release-test"),
        timeout_seconds=3600, private_key=pk,
    )
    eid = opened["escrow_id"]
    print(f"\n  opened : 0x{eid.hex()}")


    payer_sig = backend.sign_release(eid, pk)
    payee_sig = backend.sign_release(eid, pk)
    print(f"  signed : {len(payer_sig)} bytes each")

    result = backend.release_escrow(eid, payer_sig, payee_sig, DEV_ADDR, pk)
    print(f"  released tx: 0x{result['tx_hash']}")

    assert result["released"] is True
    assert result["amount"] == 50_000


    assert backend.escrow.get_escrow_confirmed(eid, expect_state="released")["state"] == "released"


def test_open_and_refund_after_deadline(setup):
    backend, pk = setup


    opened = backend.open_escrow(
        payer=DEV_ADDR, payee=DEV_ADDR, amount="0.05",
        terms_hash=Web3.keccak(text="refund-test"),
        timeout_seconds=20, private_key=pk,
    )
    eid = opened["escrow_id"]
    print(f"\n  opened : 0x{eid.hex()} (20s deadline)")

    print("  waiting for the deadline to pass...")
    time.sleep(30)

    result = backend.refund_escrow(eid, DEV_ADDR, pk)
    print(f"  refunded tx: 0x{result['tx_hash']}")

    assert result["released"] is False
    assert result["amount"] == 50_000
    assert backend.escrow.get_escrow_confirmed(eid, expect_state="refunded")["state"] == "refunded"