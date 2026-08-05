from unittest.mock import MagicMock

from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.idempotency import IdempotencyStore

REQ = {"from": "0xA", "to": "0xB", "amount": "1.0", "asset": "USDC"}


def _backend(tmp_path, store):
    b = SelfCustodyBackend.__new__(SelfCustodyBackend)
    b.chain = "base-sepolia"
    b.store = store
    b.w3 = MagicMock()
    b.client = MagicMock()
    return b


def test_confirmed_key_returns_cache_without_sending(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    cached = {"success": True, "tx_hash": "0xabc", "error": ""}
    store.mark_pending("k", REQ)
    store.mark_final("k", "confirmed", cached)

    b = _backend(tmp_path, store)
    result = b.transfer("0xA", "0xB", "1.0", "USDC",
                        private_key="x", idempotency_key="k")

    assert result == cached
    b.w3.eth.send_raw_transaction.assert_not_called()


def test_broadcast_that_landed_is_reconciled_not_resent(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    store.mark_pending("k", REQ)
    store.mark_broadcast("k", "0xhash", 5)

    b = _backend(tmp_path, store)
    b.w3.eth.get_transaction_receipt.return_value = {"status": 1}

    result = b.transfer("0xA", "0xB", "1.0", "USDC",
                        private_key="x", idempotency_key="k")

    assert result["success"] is True
    assert result["tx_hash"] == "0xhash"
    b.w3.eth.send_raw_transaction.assert_not_called()
    assert store.get("k")["status"] == "confirmed"


def test_broadcast_that_reverted_is_marked_failed(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    store.mark_pending("k", REQ)
    store.mark_broadcast("k", "0xhash", 5)

    b = _backend(tmp_path, store)
    b.w3.eth.get_transaction_receipt.return_value = {"status": 0}

    result = b.transfer("0xA", "0xB", "1.0", "USDC",
                        private_key="x", idempotency_key="k")

    assert result["success"] is False
    assert store.get("k")["status"] == "failed"