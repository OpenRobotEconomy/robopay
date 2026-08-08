"""Background resolver: autonomously confirm/recover unresolved payments.
"""
import threading
import logging

logger = logging.getLogger("robopay.resolver")


class PaymentResolver:
    def __init__(self, backend, escrow_backend=None,
                 key_provider=None, interval_seconds: float = 5.0) -> None:
        self._backend = backend
        self._escrow = escrow_backend
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._key_provider = key_provider

    def resolve_once(self) -> int:
        resolved = 0
        for record in self._backend.store.list_by_status("broadcast"):
            try:
                result = self._backend.check_status(record["key"])
                if result["status"] in ("confirmed", "failed"):
                    resolved += 1
            except Exception:
                pass
        return resolved

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        print("[resolver] loop started", flush=True)
        while not self._stop.wait(self._interval):
            try:
                self.resolve_once()
            except Exception as e:
                print(f"[resolver] resolve_once failed: {e}", flush=True)
            try:
                if self._escrow is not None:
                    self.refund_expired_escrows()
            except Exception as e:
                print(f"[resolver] escrow sweep failed: {e}", flush=True)

    def refund_expired_escrows(self) -> int:
        if self._escrow is None or self._key_provider is None:
            return 0
        import time as _time
        refunded = 0
        for rec in self._escrow.tracker.expired_unresolved(int(_time.time())):
            eid = rec["escrow_id"]
            try:
                state = self._escrow.escrow.get_escrow(eid)
                if state["state"] != "locked":
                    self._escrow.tracker.mark_resolved(eid)
                    continue
                pk = self._key_provider(rec["payer"])
                if not pk:
                    continue
                self._escrow.refund_escrow(eid, rec["payer"], pk)
                refunded += 1
                logger.info("auto-refunded expired escrow 0x%s", eid.hex()[:16])
            except Exception as e:
                logger.warning("resolve_once failed: %s", e)
        return refunded