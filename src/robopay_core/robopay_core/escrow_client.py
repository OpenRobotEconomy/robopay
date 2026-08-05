"""Thin client for the canonical RobopayEscrow contract
"""
import json
from pathlib import Path

from web3 import Web3

from .chains import CHAINS

_ABI_PATH = Path(__file__).parent / "escrow_abi.json"
ESCROW_ABI = json.loads(_ABI_PATH.read_text())


STATE_NAMES = {0: "none", 1: "locked", 2: "released", 3: "refunded"}


class EscrowClient:
    def __init__(self, chain_client, chain: str = "base-sepolia") -> None:
        self.chain = chain
        self.w3 = chain_client.w3
        address = CHAINS[chain].get("escrow")
        if not address:
            raise ValueError(f"No escrow address configured for {chain}")
        self.address = Web3.to_checksum_address(address)
        self.contract = self.w3.eth.contract(address=self.address, abi=ESCROW_ABI)

    def get_escrow(self, escrow_id: bytes) -> dict:
        e = self.contract.functions.escrows(escrow_id).call()
        return {
            "payer": e[0],
            "state": STATE_NAMES.get(e[1], "unknown"),
            "payee": e[2],
            "token": e[3],
            "amount": e[4],
            "deadline": e[5],
            "terms": e[6].hex() if isinstance(e[6], bytes) else e[6],
        }

    def release_digest(self, escrow_id: bytes) -> bytes:
        return self.contract.functions.releaseDigest(escrow_id).call()

    def is_token_allowed(self, token_address: str) -> bool:
        return self.contract.functions.allowedTokens(
            Web3.to_checksum_address(token_address)
        ).call()

    def get_escrow_confirmed(self, escrow_id: bytes, expect_state: str | None = None,
                            attempts: int = 10, delay: float = 1.0) -> dict:
        import time as _time
        last = None
        for _ in range(attempts):
            last = self.get_escrow(escrow_id)
            if expect_state is not None:
                if last["state"] == expect_state:
                    return last
            elif last["state"] != "none":
                return last
            _time.sleep(delay)
        return last