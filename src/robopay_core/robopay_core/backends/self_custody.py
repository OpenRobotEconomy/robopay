"""Self-custody settlement backend: read balances and send USDC on Base.
"""

from eth_account import Account
from web3 import Web3

from ..chain_client import ChainClient
from ..chains import token_address
from ..erc20_abi import ERC20_ABI
from ..idempotency import IdempotencyStore
from .base import PaymentBackend

from ..nonce_manager import NonceManager
from decimal import Decimal

import logging
logger = logging.getLogger("robopay.backend")




class SelfCustodyBackend(PaymentBackend):
    def __init__(self, chain: str = "base-sepolia",
                store: IdempotencyStore | None = None,
                limits=None, nonces=None) -> None:
        self.client = ChainClient(chain)
        self.w3 = self.client.w3
        self.chain = chain
        self.store = store or IdempotencyStore()
        self.nonces = nonces or NonceManager(self.w3)
        self.limits = limits

    def balance(self, address: str) -> dict:
        return {
            "USDC": self.client.token_balance(address, "USDC"),
            "ETH": self.client.native_balance(address),
        }

    def _lookup_receipt(self, tx_hash: str):
        try:
            return self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception:
            return None

    def _reconcile_broadcast(self, key: str, record: dict) -> dict | None:
        receipt = self._lookup_receipt(record["tx_hash"])
        if receipt is None:
            return None
        if receipt["status"] == 1:
            result = {"success": True, "tx_hash": record["tx_hash"], "error": ""}
            self.store.mark_final(key, "confirmed", result)
            return result
        result = {"success": False, "tx_hash": record["tx_hash"],
                  "error": "transaction reverted on-chain"}
        self.store.mark_final(key, "failed", result)
        return result


    def transfer(self, from_address: str, to_address: str,
                 amount: str, asset: str = "USDC",
                 private_key: str = "", idempotency_key: str = "",
                 reuse_nonce: int | None = None) -> dict:
        request = {"from": from_address, "to": to_address,
                   "amount": amount, "asset": asset}

        record = self.store.get(idempotency_key) if idempotency_key else None
        if record:
            status = record["status"]
            if status == "confirmed":
                return record["result"]
            if status == "broadcast":
                resolved = self._reconcile_broadcast(idempotency_key, record)
                if resolved is not None:
                    return resolved
                reuse_nonce = record["nonce"]

        if self.limits is not None:
            self.limits.check(amount)

        self.store.mark_pending(idempotency_key, request)

        sender = Web3.to_checksum_address(from_address)
        nonce = None
        try:
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address(self.chain, asset)),
                abi=ERC20_ABI,
            )
            decimals = token.functions.decimals().call()
            raw_amount = int(round(float(amount) * (10 ** decimals)))
            recipient = Web3.to_checksum_address(to_address)

            nonce = reuse_nonce if reuse_nonce is not None \
                else self.nonces.next_nonce(sender)

            tx = token.functions.transfer(recipient, raw_amount).build_transaction({
                "from": sender,
                "nonce": nonce,
                "chainId": self.client.chain_id(),
            })
            signed = Account.sign_transaction(tx, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            self.store.mark_broadcast(idempotency_key, tx_hash_hex, nonce)
            if self.limits is not None:
                self.limits.record(amount)
            return {"success": True, "status": "broadcast",
                    "tx_hash": tx_hash_hex, "error": ""}

        except Exception as e:
            if nonce is not None and reuse_nonce is None:
                try:
                    self.nonces.resync(sender)
                except Exception as resync_error:
                    logger.warning(
                        "nonce resync failed after a broadcast error - the local "
                        "counter may be out of sync with the chain: %s", resync_error)
            self.store.mark_final(idempotency_key, "failed",
                                  {"success": False, "tx_hash": "", "error": str(e)})
            return {"success": False, "status": "failed", "tx_hash": "", "error": str(e)}


    def check_status(self, idempotency_key: str) -> dict:
        record = self.store.get(idempotency_key)
        if record is None:
            return {"status": "unknown", "error": "no such payment"}
        if record["status"] in ("confirmed", "failed"):
            return {"status": record["status"], "result": record["result"]}
        if record["status"] == "broadcast":
            resolved = self._reconcile_broadcast(idempotency_key, record)
            if resolved is not None:
                return {"status": "confirmed" if resolved["success"] else "failed",
                        "result": resolved}
            return {"status": "broadcast", "tx_hash": record["tx_hash"]}
        return {"status": record["status"]}



    def preview_transfer(self, from_address: str, to_address: str,
                         amount: str, asset: str = "USDC") -> dict:
        try:
            sender = Web3.to_checksum_address(from_address)
        except Exception:
            return {"ok": False, "reason": f"invalid sender address: {from_address}",
                    "usdc_balance": "0", "gas_balance": "0", "gas_estimate": "0"}
        try:
            recipient = Web3.to_checksum_address(to_address)
        except Exception:
            return {"ok": False, "reason": f"invalid recipient address: {to_address}",
                    "usdc_balance": "0", "gas_balance": "0", "gas_estimate": "0"}

        usdc = self.client.token_balance(sender, asset)
        gas_bal = self.client.native_balance(sender)

        gas_estimate = "0"
        try:
            token = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address(self.chain, asset)),
                abi=ERC20_ABI,
            )
            decimals = token.functions.decimals().call()
            raw_amount = int(round(float(amount) * (10 ** decimals)))
            units = token.functions.transfer(recipient, raw_amount).estimate_gas(
                {"from": sender})
            price = self.w3.eth.gas_price
            gas_estimate = str(self.w3.from_wei(units * price, "ether"))
        except Exception as e:
            return {"ok": False, "reason": f"would revert: {e}",
                    "usdc_balance": usdc, "gas_balance": gas_bal,
                    "gas_estimate": "0"}

        if Decimal(usdc) < Decimal(str(amount)):
            return {"ok": False,
                    "reason": f"insufficient {asset}: have {usdc}, need {amount}",
                    "usdc_balance": usdc, "gas_balance": gas_bal,
                    "gas_estimate": gas_estimate}

        if Decimal(gas_bal) < Decimal(gas_estimate):
            return {"ok": False,
                    "reason": (f"insufficient gas: have {gas_bal} ETH, "
                               f"need about {gas_estimate} ETH"),
                    "usdc_balance": usdc, "gas_balance": gas_bal,
                    "gas_estimate": gas_estimate}

        if self.limits is not None:
            try:
                self.limits.check(amount)
            except Exception as e:
                return {"ok": False, "reason": f"spending cap: {e}",
                        "usdc_balance": usdc, "gas_balance": gas_bal,
                        "gas_estimate": gas_estimate}

        return {"ok": True, "reason": "", "usdc_balance": usdc,
                "gas_balance": gas_bal, "gas_estimate": gas_estimate}