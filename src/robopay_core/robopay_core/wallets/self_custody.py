"""Self-custody wallet provider. robopay's default backend"""
from eth_account import Account

from .base import WalletProvider
from .registry import WalletRegistry
from ..spending_limits import SpendingLimits


class SelfCustodyProvider(WalletProvider):
    def __init__(self, registry: WalletRegistry | None = None,
                 limits: SpendingLimits | None = None) -> None:
        self._account = None
        self._registry = registry or WalletRegistry()
        self.limits = limits or SpendingLimits()

    def create(self, label: str = "robot", passphrase: str = "") -> str:
        self._account = Account.create()
        self._registry.save(
            self._account.address, "0x" + self._account.key.hex(),
            passphrase, label,
        )
        return self._account.address

    def load(self, address: str, passphrase: str) -> str:
        """Load a previously-saved wallet back into memory."""
        pk = self._registry.load_private_key(address, passphrase)
        self._account = Account.from_key(pk)
        return self._account.address

    def address(self) -> str:
        return self._account.address if self._account else ""

    def private_key(self) -> str:
        if not self._account:
            raise RuntimeError("No wallet - call create() or load() first.")
        return "0x" + self._account.key.hex()

    def verify_passphrase(self, passphrase: str) -> bool:
        for w in self._registry.list_wallets():
            try:
                self._registry.load_private_key(w["address"], passphrase)
                return True
            except Exception:
                continue
        return False