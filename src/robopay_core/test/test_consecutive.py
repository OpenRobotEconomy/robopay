import os
import uuid

import pytest

from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.wallets.self_custody import SelfCustodyProvider

DEV_ADDR = os.getenv("ROBOPAY_TEST_ADDRESS", "")
DEV_PASS = os.getenv("ROBOPAY_TEST_PASSPHRASE", "")

pytestmark = pytest.mark.skipif(
    not DEV_ADDR, reason="set ROBOPAY_TEST_ADDRESS to run the live consecutive test"
)


def test_five_in_a_row_all_broadcast():
    backend = SelfCustodyBackend("base-sepolia")
    w = SelfCustodyProvider()
    w.load(DEV_ADDR, DEV_PASS)
    pk = w.private_key()

    results = []
    for i in range(5):
        r = backend.transfer(
            from_address=DEV_ADDR,
            to_address="0x000000000000000000000000000000000000dEaD",
            amount="0.01",
            asset="USDC",
            private_key=pk,
            idempotency_key=f"consec-{uuid.uuid4()}",
        )
        results.append(r)


    assert all(r["success"] for r in results), results
    hashes = [r["tx_hash"] for r in results]
    assert len(set(hashes)) == 5
    print("\nbroadcast 5 txs:", *hashes, sep="\n  ")