from robopay_core.idempotency import IdempotencyStore

REQ = {"from": "0xA", "to": "0xB", "amount": "1.0", "asset": "USDC"}


def test_unseen_key_returns_none(tmp_path):
    s = IdempotencyStore(tmp_path / "p.db")
    assert s.get("never-seen") is None


def test_full_lifecycle(tmp_path):
    s = IdempotencyStore(tmp_path / "p.db")
    s.mark_pending("k1", REQ)
    assert s.get("k1")["status"] == "pending"
    assert s.get("k1")["request"] == REQ

    s.mark_broadcast("k1", "0xhash", 7)
    rec = s.get("k1")
    assert rec["status"] == "broadcast"
    assert rec["tx_hash"] == "0xhash"
    assert rec["nonce"] == 7

    s.mark_final("k1", "confirmed", {"success": True, "tx_hash": "0xhash"})
    rec = s.get("k1")
    assert rec["status"] == "confirmed"
    assert rec["result"]["success"] is True


def test_pending_is_not_overwritten_by_retry(tmp_path):
    s = IdempotencyStore(tmp_path / "p.db")
    s.mark_pending("k1", REQ)
    s.mark_broadcast("k1", "0xhash", 7)
    s.mark_pending("k1", {"different": "request"})
    assert s.get("k1")["status"] == "broadcast"
    assert s.get("k1")["tx_hash"] == "0xhash"


def test_survives_reopen(tmp_path):
    db = tmp_path / "p.db"
    s1 = IdempotencyStore(db)
    s1.mark_pending("k1", REQ)
    s1.mark_broadcast("k1", "0xhash", 7)
    s1.close()

    s2 = IdempotencyStore(db)
    rec = s2.get("k1")
    assert rec["status"] == "broadcast"
    assert rec["tx_hash"] == "0xhash"
    assert rec["nonce"] == 7