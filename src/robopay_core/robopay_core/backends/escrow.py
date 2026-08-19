"""Escrow operations against the canonical RobopayEscrow contract.
"""
import time

from eth_account import Account
from web3 import Web3
from web3.logs import DISCARD

from ..chain_client import ChainClient
from ..chains import token_address
from ..erc20_abi import ERC20_ABI
from ..escrow_client import EscrowClient
from ..nonce_manager import NonceManager
from ..escrow_signing import sign_release as _sign_release

from ..escrow_tracker import EscrowTracker


DEFAULT_APPROVAL = 1_000_000_000
GAS_LIMIT_APPROVE = 100_000
GAS_LIMIT_OPEN = 300_000
GAS_LIMIT_RELEASE = 250_000
GAS_LIMIT_REFUND = 150_000


class EscrowBackend:
    def __init__(self, chain="base-sepolia", nonce_manager=None, limits=None):
        self.chain = chain
        self.client = ChainClient(chain)
        self.w3 = self.client.w3
        self.escrow = EscrowClient(self.client, chain)
        if nonce_manager is None:
            raise ValueError(
                "EscrowBackend requires a nonce_manager shared with the transfer "
                "backend. Two managers for one wallet hand out colliding nonces.")
        self.nonces = nonce_manager
        self.tracker = EscrowTracker()
        self.limits = limits


    def _token(self, asset: str = "USDC"):
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address(self.chain, asset)),
            abi=ERC20_ABI,
        )

    def _send(self, tx: dict, private_key: str):
        try:
            signed = Account.sign_transaction(tx, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        except Exception as e:
            if "nonce too low" not in str(e).lower():
                raise
            sender = tx["from"]
            new_nonce = self.nonces.resync(sender)
            tx = dict(tx, nonce=new_nonce)
            signed = Account.sign_transaction(tx, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"transaction reverted: {tx_hash.hex()}")
        return receipt


    def _ensure_approval(self, owner: str, amount: int, private_key: str,
                         asset: str = "USDC") -> None:
        token = self._token(asset)
        owner = Web3.to_checksum_address(owner)
        current = token.functions.allowance(owner, self.escrow.address).call()
        if current >= amount:
            return
        tx = token.functions.approve(
            self.escrow.address, max(DEFAULT_APPROVAL, amount)
        ).build_transaction({
            "from": owner,
            "nonce": self.nonces.next_nonce(owner),
            "chainId": self.client.chain_id(),
            "gas": GAS_LIMIT_APPROVE,
        })
        self._send(tx, private_key)


    def open_escrow(self, payer: str, payee: str, amount: str,
                    terms_hash: bytes, timeout_seconds: float,
                    private_key: str, asset: str = "USDC") -> dict:

        payer = Web3.to_checksum_address(payer)
        payee = Web3.to_checksum_address(payee)
        token = self._token(asset)
        decimals = token.functions.decimals().call()
        raw_amount = int(round(float(amount) * (10 ** decimals)))
        deadline = int(time.time() + timeout_seconds)

        if self.limits is not None:
            self.limits.check(amount)

        self._ensure_approval(payer, raw_amount, private_key, asset)

        tx = self.escrow.contract.functions.open(
            payee,
            token.address,
            raw_amount,
            deadline,
            terms_hash,
            int(time.time() * 1000),
        ).build_transaction({
            "from": payer,
            "nonce": self.nonces.next_nonce(payer),
            "chainId": self.client.chain_id(),
            "gas": GAS_LIMIT_OPEN,
        })
        receipt = self._send(tx, private_key)

        events = self.escrow.contract.events.Opened().process_receipt(
            receipt, errors=DISCARD)
        if not events:
            raise RuntimeError("open succeeded but no Opened event found")
        args = events[0]["args"]

        if self.limits is not None:
            self.limits.record(amount)

        self.tracker.track(args["id"], args["payer"], args["deadline"])

        return {
            "escrow_id": args["id"],
            "payer": args["payer"],
            "payee": args["payee"],
            "token": args["token"],
            "amount": args["amount"],
            "deadline": args["deadline"],
            "terms": args["terms"],
            "tx_hash": receipt["transactionHash"].hex(),
        }


    def sign_release(self, escrow_id: bytes, private_key: str) -> bytes:
        escrow = self.escrow.get_escrow_confirmed(escrow_id)
        if escrow["state"] != "locked":
            raise RuntimeError(f"escrow is {escrow['state']}, not locked")
        return _sign_release(
            private_key, self.client.chain_id(), self.escrow.address,
            escrow, escrow_id,
        )


    def release_escrow(self, escrow_id: bytes, payer_sig: bytes,
                       payee_sig: bytes, sender: str,
                       private_key: str) -> dict:
        sender = Web3.to_checksum_address(sender)
        tx = self.escrow.contract.functions.release(
            escrow_id, payer_sig, payee_sig
        ).build_transaction({
            "from": sender,
            "nonce": self.nonces.next_nonce(sender),
            "chainId": self.client.chain_id(),
            "gas": GAS_LIMIT_RELEASE,
        })
        receipt = self._send(tx, private_key)

        events = self.escrow.contract.events.Released().process_receipt(
            receipt, errors=DISCARD)
        if not events:
            raise RuntimeError("release succeeded but no Released event found")
        args = events[0]["args"]
        self.tracker.mark_resolved(escrow_id)
        return {
            "escrow_id": args["id"],
            "payee": args["payee"],
            "amount": args["amount"],
            "tx_hash": receipt["transactionHash"].hex(),
            "released": True,
        }


    def refund_escrow(self, escrow_id: bytes, sender: str,
                      private_key: str) -> dict:
        sender = Web3.to_checksum_address(sender)
        tx = self.escrow.contract.functions.refund(escrow_id).build_transaction({
            "from": sender,
            "nonce": self.nonces.next_nonce(sender),
            "chainId": self.client.chain_id(),
            "gas": GAS_LIMIT_REFUND,
        })
        receipt = self._send(tx, private_key)

        events = self.escrow.contract.events.Refunded().process_receipt(
            receipt, errors=DISCARD)
        if not events:
            raise RuntimeError("refund succeeded but no Refunded event found")
        args = events[0]["args"]

        self.tracker.mark_resolved(escrow_id)

        return {
            "escrow_id": args["id"],
            "payer": args["payer"],
            "amount": args["amount"],
            "tx_hash": receipt["transactionHash"].hex(),
            "released": False,
        }