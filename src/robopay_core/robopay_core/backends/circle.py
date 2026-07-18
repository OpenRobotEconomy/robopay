"""Circle settlement backend (implemented in Phase 8) — the opt-in managed path.

Wraps Circle Developer-Controlled Wallets (MPC custody, gas abstraction). The
Entity Secret comes from the environment, never from code or a ROS topic.
"""
from .base import PaymentBackend

_TODO = "CircleBackend lands in Phase 8 (circle-developer-controlled-wallets)."


class CircleBackend(PaymentBackend):
    def balance(self, address: str) -> dict:
        raise NotImplementedError(_TODO)

    def transfer(self, from_address, to_address, amount, asset="USDC") -> dict:
        raise NotImplementedError(_TODO)
