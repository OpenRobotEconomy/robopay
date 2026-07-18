"""Self-custody wallet provider — robopay's DEFAULT real backend.

The robot holds its own key locally, fully peer-to-peer, no account needed.
This Phase-0 stub returns a placeholder address; Phase 2 replaces it with real
secp256k1 keygen (eth-account), an encrypted-at-rest registry, and web3.py
signing against a public Base RPC.
"""
import secrets

from .base import WalletProvider


class SelfCustodyProvider(WalletProvider):
    def __init__(self) -> None:
        self._address: str | None = None

    def create(self, label: str = "robot") -> str:
        self._address = "0x" + secrets.token_hex(20)  # placeholder — Phase 2 = real keygen
        return self._address

    def address(self) -> str:
        return self._address or ""
