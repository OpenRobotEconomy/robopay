"""robopay payment node.
Exposes wallet and transfer services over ROS.
"""

import logging
import time
import uuid

import rclpy
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from robopay_interfaces.action import Escrow
from robopay_interfaces.msg import EscrowSignature
from robopay_interfaces.srv import (
    EscrowSign,
    EscrowSubmitSignature,
    Transfer,
    TransferPreview,
    WalletBalance,
    WalletCreate,
)

from robopay_core.backends.escrow import EscrowBackend
from robopay_core.backends.mock import MockBackend
from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.resolver import PaymentResolver
from robopay_core.secrets import PassphraseUnavailable, get_passphrase
from robopay_core.signature_store import SignatureStore
from robopay_core.spending_limits import SpendingLimitExceeded, SpendingLimits
from robopay_core.wallets.self_custody import SelfCustodyProvider
from robopay_core.chain_client import ChainClient
from robopay_core.nonce_manager import NonceManager
from robopay_interfaces.msg import EscrowSignature, PaymentRequest as PaymentRequestMsg
from robopay_core.invoice import Invoice, InvalidInvoice



class PaymentNode(Node):
    def __init__(self) -> None:
        super().__init__("payment_node")

        self.declare_parameter("backend", "self_custody")   # mock | self_custody
        self.declare_parameter("chain", "base-sepolia")
        self.declare_parameter("signature_exchange", "topic")   # topic | manual
        self.declare_parameter("max_per_transaction", "10")
        self.declare_parameter("max_per_window", "50")
        self.declare_parameter("window_seconds", 3600.0)

        self._backend_name = self.get_parameter("backend").value
        chain = self.get_parameter("chain").value
        self._sig_exchange = self.get_parameter("signature_exchange").value
        is_self_custody = self._backend_name == "self_custody"

        try:
            self._passphrase = get_passphrase()
        except PassphraseUnavailable as e:
            self._passphrase = ""
            self.get_logger().warn(f"wallet locked: {e}")

        limits = SpendingLimits(
            max_per_transaction=self.get_parameter("max_per_transaction").value,
            max_per_window=self.get_parameter("max_per_window").value,
            window_seconds=self.get_parameter("window_seconds").value,
        )
        self.wallet = SelfCustodyProvider(limits=limits)
        self.signatures = SignatureStore()
        self.escrow_backend = None
        self.resolver = None
        self._sig_pub = None
        self._invoice_pub = None

        if is_self_custody:
            self._report_wallet_status()
            nonces = NonceManager(ChainClient(chain).w3)
            self.wallet.nonces = nonces
            self.backend = SelfCustodyBackend(chain, limits=limits, nonces=nonces)
            self.escrow_backend = EscrowBackend(chain, nonces=nonces, limits=limits)
            self.resolver = PaymentResolver(
                self.backend, self.escrow_backend, key_provider=self._key_for)
            self.resolver.start()
            self.get_logger().info(
                f"payment_node up (self_custody, {chain}, resolver running) | "
                f"caps: {limits.max_per_transaction}/tx, "
                f"{limits.max_per_window} per {int(limits.window_seconds)}s")
        else:
            self.backend = MockBackend()
            self.get_logger().info("payment_node up (mock backend)")

        self.create_service(WalletCreate, "wallet/create", self._on_wallet_create)
        self.create_service(WalletBalance, "wallet/balance", self._on_wallet_balance)
        self.create_service(Transfer, "transfer/send", self._on_transfer)
        self.create_service(TransferPreview, "transfer/preview", self._on_preview)

        if is_self_custody:
            self.create_service(EscrowSign, "escrow/sign", self._on_escrow_sign)
            self.create_service(EscrowSubmitSignature, "escrow/submit_signature",
                                self._on_submit_signature)
            self._escrow_cb_group = ReentrantCallbackGroup()
            self._escrow_action = ActionServer(
                self, Escrow, "escrow", self._execute_escrow,
                callback_group=self._escrow_cb_group)
            self.get_logger().info("escrow services ready")

            if self._sig_exchange == "topic":
                self._sig_pub = self.create_publisher(
                    EscrowSignature, "escrow/signatures", 10)
                self.create_subscription(
                    EscrowSignature, "escrow/signatures",
                    self._on_signature_msg, 10)
                self.get_logger().info("signature exchange: topic")
            else:
                self.get_logger().info("signature exchange: manual (services only)")

            self._invoice_pub = self.create_publisher(
                PaymentRequestMsg, "/payment_requests", 10)
            self.create_subscription(
                PaymentRequestMsg, "/payment_requests",
                self._on_invoice, 10)
            self.get_logger().info("invoices: /payment_requests")



    def _report_wallet_status(self) -> None:
        """Tell the operator plainly whether signing will work."""
        if not self.wallet._registry.list_wallets():
            self.get_logger().warn(
                "no wallets found - create one with `robopay wallet create`")
        elif not self._passphrase:
            self.get_logger().warn(
                "LOCKED: no passphrase - reads work, signing will fail")
        elif not self.wallet.verify_passphrase(self._passphrase):
            self.get_logger().error(
                "LOCKED: passphrase does not unlock any stored wallet. "
                "Balances and reads work; transfers and escrow will fail.")
        else:
            self.get_logger().info("wallet unlocked")

    def _key_for(self, address: str) -> str:
        """Unlock a wallet on demand (used by the resolver for auto-refunds)."""
        try:
            self.wallet.load(address, self._passphrase)
            return self.wallet.private_key()
        except Exception:
            return ""

    def _log_cap_block(self, error: Exception) -> None:
        lim = self.wallet.limits
        self.get_logger().warn(
            f"BLOCKED by spending cap: {error} | caps: "
            f"{lim.max_per_transaction}/tx, {lim.max_per_window} per "
            f"{int(lim.window_seconds)}s ({lim.spent_in_window()} spent). "
            f"Raise with -p max_per_transaction / -p max_per_window.")

    @staticmethod
    def _parse_escrow_id(value: str) -> bytes:
        eid = bytes.fromhex(value.removeprefix("0x"))
        if len(eid) != 32:
            raise ValueError(
                f"escrow_id must be 32 bytes (64 hex chars), got {len(eid)}")
        return eid


    def _on_wallet_create(self, request, response):
        try:
            addr = self.wallet.create(request.label or "robot", self._passphrase)
            if self._backend_name == "mock":
                self.backend.fund(addr, 100.0)   # seed fake funds for mock only
            response.success = True
            response.address = addr
            response.label = request.label
        except Exception as e:
            response.success = False
            response.error = str(e)
        return response

    def _on_wallet_balance(self, request, response):
        try:
            bal = self.backend.balance(request.address)
            response.success = True
            response.usdc = str(bal.get("USDC", "0"))
            response.gas = str(bal.get("ETH", "0"))
            response.error = ""
        except Exception as e:
            response.success = False
            response.error = str(e)
        return response


    def _on_transfer(self, request, response):
        try:
            kwargs = {}
            if self._backend_name == "self_custody":
                self.wallet.load(request.from_address, self._passphrase)
                kwargs["private_key"] = self.wallet.private_key()
                kwargs["idempotency_key"] = (
                    request.idempotency_key or f"auto-{uuid.uuid4()}")
            result = self.backend.transfer(
                request.from_address, request.to_address,
                request.amount, request.asset or "USDC", **kwargs,
            )
            response.success = result["success"]
            response.tx_hash = result["tx_hash"]
            response.error = result["error"]
        except SpendingLimitExceeded as e:
            self._log_cap_block(e)
            response.success = False
            response.error = str(e)
        except Exception as e:
            self.get_logger().error(f"transfer failed: {e}")
            response.success = False
            response.error = str(e)
        return response


    def _on_escrow_sign(self, request, response):
        try:
            eid = self._parse_escrow_id(request.escrow_id)
            addr = request.signer_address or self.wallet.address()
            self.wallet.load(addr, self._passphrase)
            sig = self.escrow_backend.sign_release(eid, self.wallet.private_key())

            response.success = True
            response.signature = "0x" + sig.hex()
            response.signer = addr
            response.error = ""

            if self._sig_pub is not None:
                out = EscrowSignature()
                out.escrow_id = request.escrow_id
                out.role = request.role
                out.signature = response.signature
                out.signer = addr
                self._sig_pub.publish(out)
        except Exception as e:
            self.get_logger().error(f"escrow sign failed: {e}")
            response.success = False
            response.error = str(e)
        return response

    def _on_submit_signature(self, request, response):
        try:
            eid = self._parse_escrow_id(request.escrow_id)
            sig = bytes.fromhex(request.signature.removeprefix("0x"))
            if len(sig) != 65:
                raise ValueError(f"signature must be 65 bytes, got {len(sig)}")
            self.signatures.add(eid, request.role, sig)
            self.get_logger().info(
                f"signature stored: {request.role} for 0x{eid.hex()[:16]}...")
            response.accepted = True
            response.error = ""
        except Exception as e:
            response.accepted = False
            response.error = str(e)
        return response

    def _on_signature_msg(self, msg: EscrowSignature) -> None:
        """Handle a signature broadcast by a peer. UNTRUSTED INPUT: validate the
        shape and ignore anything malformed; the contract is the real check."""
        try:
            eid = bytes.fromhex(msg.escrow_id.removeprefix("0x"))
            if len(eid) != 32 or msg.role not in ("payer", "payee"):
                return
            sig = bytes.fromhex(msg.signature.removeprefix("0x"))
            if len(sig) != 65:
                return
            if msg.role in self.signatures.get(eid):
                return      # already have this role

            self.signatures.add(eid, msg.role, sig)
            self.get_logger().info(
                f"signature received via topic: {msg.role} for 0x{eid.hex()[:16]}...")
        except Exception as e:
            self.get_logger().warn(f"ignoring malformed signature message: {e}")



    def _execute_escrow(self, goal_handle):
        goal = goal_handle.request
        result = Escrow.Result()
        feedback = Escrow.Feedback()
        eid_hex = ""

        def report(state: str, detail: str = "", escrow_id: str = ""):
            feedback.escrow_id = escrow_id
            feedback.state = state
            feedback.detail = detail
            goal_handle.publish_feedback(feedback)

        try:
            report("opening")
            self.wallet.load(goal.from_address, self._passphrase)
            pk = self.wallet.private_key()
            terms = (bytes.fromhex(goal.terms_hash.removeprefix("0x"))
                     if goal.terms_hash else bytes(32))

            opened = self.escrow_backend.open_escrow(
                payer=goal.from_address,
                payee=goal.to_address,
                amount=goal.amount,
                terms_hash=terms,
                timeout_seconds=goal.timeout_seconds,
                private_key=pk,
                asset=goal.asset or "USDC",
            )
            eid = opened["escrow_id"]
            eid_hex = "0x" + eid.hex()
            deadline = opened["deadline"]

            self.get_logger().info(
                f"escrow opened: {eid_hex} ({goal.amount} {goal.asset or 'USDC'} "
                f"to {goal.to_address[:10]}..., "
                f"expires in {int(goal.timeout_seconds)}s)")
            report("locked", f"amount={goal.amount}", eid_hex)
            report("awaiting_proof", "", eid_hex)

            announced_partial = False
            while True:
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.released = False
                    result.escrow_id = eid_hex
                    result.status = "cancelled"
                    return result

                sigs = self.signatures.get(eid)
                if len(sigs) == 1 and not announced_partial:
                    have = next(iter(sigs))
                    report("proof_partial",
                           f"have {have}, waiting for the other", eid_hex)
                    announced_partial = True

                if self.signatures.has_both(eid):
                    report("releasing", "", eid_hex)
                    rel = self.escrow_backend.release_escrow(
                        eid, sigs["payer"], sigs["payee"], goal.from_address, pk)
                    self.signatures.clear(eid)
                    goal_handle.succeed()
                    result.released = True
                    result.escrow_id = eid_hex
                    result.status = "released"
                    result.tx_hash = "0x" + rel["tx_hash"]
                    self.get_logger().info(f"escrow released: {eid_hex}")
                    return result

                if time.time() > deadline:
                    report("timed_out", "deadline passed, refunding", eid_hex)
                    report("refunding", "", eid_hex)
                    ref = self.escrow_backend.refund_escrow(
                        eid, goal.from_address, pk)
                    self.signatures.clear(eid)
                    goal_handle.succeed()
                    result.released = False
                    result.escrow_id = eid_hex
                    result.status = "refunded_timeout"
                    result.tx_hash = "0x" + ref["tx_hash"]
                    self.get_logger().info(f"escrow refunded (timeout): {eid_hex}")
                    return result

                time.sleep(1.0)

        except SpendingLimitExceeded as e:
            self._log_cap_block(e)
            goal_handle.abort()
            result.released = False
            result.escrow_id = eid_hex
            result.status = "failed"
            result.error = str(e)
            return result
        except Exception as e:
            self.get_logger().error(f"escrow failed: {e}")
            goal_handle.abort()
            result.released = False
            result.escrow_id = eid_hex
            result.status = "failed"
            result.error = str(e)
            return result

    def _on_preview(self, request, response):
        """Free dry run"""
        try:
            if self._backend_name != "self_custody":
                response.ok = True
                response.reason = "mock backend: preview always passes"
                return response
            result = self.backend.preview_transfer(
                request.from_address, request.to_address,
                request.amount, request.asset or "USDC")
            response.ok = result["ok"]
            response.reason = result["reason"]
            response.usdc_balance = result["usdc_balance"]
            response.gas_balance = result["gas_balance"]
            response.gas_estimate = result["gas_estimate"]
        except Exception as e:
            response.ok = False
            response.reason = str(e)
        return response

    def _on_invoice(self, msg: PaymentRequestMsg) -> None:
        try:
            inv = Invoice.parse({
                "request_id": msg.request_id,
                "payee_address": msg.payee_address,
                "amount": msg.amount,
                "asset": msg.asset,
                "memo": msg.memo,
                "settlement": msg.settlement,
                "terms_hash": msg.terms_hash,
            })
        except InvalidInvoice as e:
            self.get_logger().warn(f"ignoring malformed invoice: {e}")
            return

        self.get_logger().info(
            f"invoice received: {inv.amount} {inv.asset} to "
            f"{inv.payee_address[:10]}... via {inv.settlement} "
            f"[{inv.memo}] (id {inv.request_id[:8]})")

    def publish_invoice(self, payee: str, amount: str, memo: str = "",
                        settlement: str = "direct", asset: str = "USDC",
                        terms_hash: str = "") -> str:
        inv = Invoice.create(payee=payee, amount=amount, memo=memo,
                             settlement=settlement, asset=asset,
                             terms_hash=terms_hash)
        if self._invoice_pub is None:
            raise RuntimeError("invoice publishing is not enabled")

        out = PaymentRequestMsg()
        out.request_id = inv.request_id
        out.payee_address = inv.payee_address
        out.amount = inv.amount
        out.asset = inv.asset
        out.memo = inv.memo
        out.settlement = inv.settlement
        out.terms_hash = inv.terms_hash
        self._invoice_pub.publish(out)

        self.get_logger().info(f"invoice published: {inv.amount} {inv.asset} "
                               f"[{inv.memo}] (id {inv.request_id[:8]})")
        return inv.request_id


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="[%(name)s] %(levelname)s: %(message)s")
    rclpy.init()
    node = PaymentNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(node, "resolver", None):
            node.resolver.stop()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()