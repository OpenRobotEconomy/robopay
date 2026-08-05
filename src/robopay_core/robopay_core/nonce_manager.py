"""Per-wallet local nonce tracking, so consecutive transfers don't collide.
"""
import threading


class NonceManager:
    def __init__(self, w3) -> None:
        self._w3 = w3
        self._next: dict[str, int] = {}
        self._lock = threading.Lock()

    def _chain_nonce(self, address: str) -> int:
        return self._w3.eth.get_transaction_count(address, "pending")

    def next_nonce(self, address: str) -> int:
        with self._lock:
            if address not in self._next:
                self._next[address] = self._chain_nonce(address)  # seed once
            nonce = self._next[address]
            self._next[address] = nonce + 1
            return nonce

    def resync(self, address: str) -> int:
        with self._lock:
            fresh = self._chain_nonce(address)
            self._next[address] = fresh
            return fresh