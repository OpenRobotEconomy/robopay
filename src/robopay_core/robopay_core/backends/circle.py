"""Circle settlement backend
Wraps Circle Developer-Controlled Wallets
"""
from .base import PaymentBackend

_TODO = "CircleBackend lands in Phase 8 (circle-developer-controlled-wallets)."


class CircleBackend(PaymentBackend):
    def balance(self, address: str) -> dict:
        raise NotImplementedError(_TODO)

    def transfer(self, from_address, to_address, amount, asset="USDC") -> dict:
        raise NotImplementedError(_TODO)
