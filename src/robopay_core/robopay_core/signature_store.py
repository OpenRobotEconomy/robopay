"""In-memory store of escrow release signatures, keyed by escrow id.

Signatures arrive asynchronously (via the submit_signature service, or the
topic layer in 4.4B) while an Escrow action waits for them. This decouples the
two: submitters write here, the waiting action polls here. Signatures that
arrive BEFORE the action starts waiting are still captured.
"""
import threading


class SignatureStore:
    def __init__(self) -> None:
        self._sigs: dict[bytes, dict[str, bytes]] = {}
        self._lock = threading.Lock()

    def add(self, escrow_id: bytes, role: str, signature: bytes) -> None:
        if role not in ("payer", "payee"):
            raise ValueError(f"role must be payer or payee, got {role}")
        with self._lock:
            self._sigs.setdefault(escrow_id, {})[role] = signature

    def get(self, escrow_id: bytes) -> dict[str, bytes]:
        with self._lock:
            return dict(self._sigs.get(escrow_id, {}))

    def has_both(self, escrow_id: bytes) -> bool:
        sigs = self.get(escrow_id)
        return "payer" in sigs and "payee" in sigs

    def clear(self, escrow_id: bytes) -> None:
        with self._lock:
            self._sigs.pop(escrow_id, None)