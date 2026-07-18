"""Self-custody settlement backend (implemented in Phase 2).

Signs and sends USDC transactions with a locally-held key via web3.py against a
public Base RPC. Stubbed here so payment_node can target the interface now; the
real implementation slots in without changing anything above it.
"""
from .base import PaymentBackend

_TODO = "SelfCustodyBackend lands in Phase 2 (web3.py + Base RPC)."


class SelfCustodyBackend(PaymentBackend):
    def balance(self, address: str) -> dict:
        raise NotImplementedError(_TODO)

    def transfer(self, from_address, to_address, amount, asset="USDC") -> dict:
        raise NotImplementedError(_TODO)
