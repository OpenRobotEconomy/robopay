"""Settlement backend interface.
An implementation targets one rail (self-custody via web3.py, Circle, or the
in-memory mock used for tests).
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
