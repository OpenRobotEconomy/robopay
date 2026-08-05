from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.idempotency import IdempotencyStore
from robopay_core.resolver import PaymentResolver

REQ = {"from": "0xA", "to": "0xB", "amount": "1.0", "asset": "USDC"}


def _backend(store, receipt):
    b = SelfCustodyBackend.__new__(SelfCustodyBackend)
    b.store = store
    b.chain = "base-sepolia"
    b._lookup_receipt = lambda tx_hash: receipt
    return b


def test_resolver_confirms_a_landed_payment(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    store.mark_pending("k", REQ)
    store.mark_broadcast("k", "0xhash", 3)

    backend = _backend(store, {"status": 1})
    resolver = PaymentResolver(backend)

    n = resolver.resolve_once()
    assert n == 1
    assert store.get("k")["status"] == "confirmed"


def test_resolver_leaves_still_pending_alone(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    store.mark_pending("k", REQ)
    store.mark_broadcast("k", "0xhash", 3)

    backend = _backend(store, None)
    resolver = PaymentResolver(backend)

    n = resolver.resolve_once()
    assert n == 0
    assert store.get("k")["status"] == "broadcast"


def test_nothing_to_resolve(tmp_path):
    store = IdempotencyStore(tmp_path / "p.db")
    backend = _backend(store, None)
    assert PaymentResolver(backend).resolve_once() == 0