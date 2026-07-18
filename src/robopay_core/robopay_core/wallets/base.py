"""Custody abstraction (the WalletProvider seam).

Implementations decide where keys live and who signs:
SelfCustodyProvider (the default), and a Circle-backed provider (opt-in).
Keys never cross ROS — only addresses do.
"""
from abc import ABC, abstractmethod


class WalletProvider(ABC):
    @abstractmethod
    def create(self, label: str) -> str:
        """Provision a wallet and return its public address."""

    @abstractmethod
    def address(self) -> str:
        """Return the current public address."""
