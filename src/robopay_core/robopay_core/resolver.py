"""Background resolver: autonomously confirm/recover unresolved payments.
"""
import threading


class PaymentResolver:
    def __init__(self, backend, interval_seconds: float = 5.0) -> None:
        self._backend = backend
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

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
        while not self._stop.wait(self._interval):
            try:
                self.resolve_once()
            except Exception:
                pass