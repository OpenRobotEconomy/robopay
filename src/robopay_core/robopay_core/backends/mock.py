"""Deterministic in-memory backend.
Spends no real money and needs no chain"""
from .base import PaymentBackend


class MockBackend(PaymentBackend):
    def __init__(self) -> None:
        self._balances: dict[str, dict[str, float]] = {}

    def fund(self, address: str, amount: float, asset: str = "USDC") -> None:
        self._balances.setdefault(address, {}).setdefault(asset, 0.0)
        self._balances[address][asset] += float(amount)

    def balance(self, address: str) -> dict:
        return self._balances.get(address, {})

    def transfer(self, from_address: str, to_address: str,
                 amount: str, asset: str = "USDC") -> dict:
        amt = float(amount)
        have = self._balances.get(from_address, {}).get(asset, 0.0)
        if have < amt:
            return {"success": False, "tx_hash": "", "error": "insufficient_funds"}
        self._balances[from_address][asset] -= amt
        self.fund(to_address, amt, asset)
        return {"success": True,
                "tx_hash": f"mock-{from_address[:6]}->{to_address[:6]}:{amount}",
                "error": ""}
