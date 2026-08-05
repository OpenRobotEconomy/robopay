import os

import pytest

from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.idempotency import IdempotencyStore
from robopay_core.wallets.self_custody import SelfCustodyProvider


DEV_ADDR = os.getenv("ROBOPAY_TEST_ADDRESS", "")
DEV_PASS = os.getenv("ROBOPAY_TEST_PASSPHRASE", "")

pytestmark = pytest.mark.skipif(
    not DEV_ADDR, reason="set ROBOPAY_TEST_ADDRESS to run the live lifecycle test"
)


def test_transfer_records_full_lifecycle(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    backend = SelfCustodyBackend("base-sepolia", store=store)

    w = SelfCustodyProvider()
    w.load(DEV_ADDR, DEV_PASS)

    key = "test-lifecycle-001"
    result = backend.transfer(
        from_address=DEV_ADDR,
        to_address="0x000000000000000000000000000000000000dEaD",
        amount="0.1",
        asset="USDC",
        private_key=w.private_key(),
        idempotency_key=key,
    )

    assert result["success"] is True
    rec = store.get(key)
    assert rec["status"] == "confirmed"
    assert rec["tx_hash"]
    assert rec["nonce"] is not None
    assert rec["result"]["success"] is True