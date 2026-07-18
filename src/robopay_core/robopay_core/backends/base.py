"""Settlement backend interface.

An implementation targets one rail (self-custody via web3.py, Circle, or the
in-memory mock used for tests). payment_node only ever talks to this interface,
which is what keeps robopay chain-agnostic.
"""
from abc import ABC, abstractmethod


class PaymentBackend(ABC):
    @abstractmethod
    def balance(self, address: str) -> dict:
        """Return {asset: amount} held by ``address``."""

    @abstractmethod
    def transfer(self, from_address: str, to_address: str,
                 amount: str, asset: str) -> dict:
        """Move ``amount`` of ``asset``. Return {success, tx_hash, error}."""
