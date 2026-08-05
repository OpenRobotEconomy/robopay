"""Custody abstraction (WalletProvider seam).
"""
from abc import ABC, abstractmethod


class WalletProvider(ABC):
    @abstractmethod
    def create(self, label: str) -> str:
        """Provision a wallet and return its public address."""

    @abstractmethod
    def address(self) -> str:
        """Return the current public address."""
