"""robopay payment node.
Exposes wallet and transfer services over ROS.
"""


import rclpy
from rclpy.node import Node

from robopay_interfaces.srv import Transfer, WalletBalance, WalletCreate

from robopay_core.backends.mock import MockBackend
from robopay_core.backends.self_custody import SelfCustodyBackend
from robopay_core.wallets.self_custody import SelfCustodyProvider
from robopay_core.resolver import PaymentResolver

from robopay_interfaces.srv import EscrowSign, EscrowSubmitSignature

from robopay_core.backends.escrow import EscrowBackend
from robopay_core.signature_store import SignatureStore

import uuid

import time

from rclpy.action import ActionServer

from robopay_interfaces.action import Escrow

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor


class PaymentNode(Node):
    def __init__(self) -> None:
        super().__init__("payment_node")

        self.declare_parameter("backend", "self_custody")          # "mock" | "self_custody"
        self.declare_parameter("chain", "base-sepolia")
        self.declare_parameter("passphrase", "")
        backend_name = self.get_parameter("backend").value
        chain = self.get_parameter("chain").value
        self._passphrase = self.get_parameter("passphrase").value

        self.wallet = SelfCustodyProvider()

        if backend_name == "self_custody":
            self.backend = SelfCustodyBackend(chain)
            self.resolver = PaymentResolver(self.backend)
            self.resolver.start()
            self.get_logger().info(
                f"payment_node up (self_custody, {chain}, resolver running)")
        else:
            self.backend = MockBackend()
            self.resolver = None
            self.get_logger().info("payment_node up (mock backend)")
        self._backend_name = backend_name

        self.create_service(WalletCreate, "wallet/create", self._on_wallet_create)
        self.create_service(WalletBalance, "wallet/balance", self._on_wallet_balance)
        self.create_service(Transfer, "transfer/send", self._on_transfer)

        self.signatures = SignatureStore()
        self.escrow_backend = None
        if backend_name == "self_custody":
            self.escrow_backend = EscrowBackend(chain)
            self.create_service(EscrowSign, "escrow/sign", self._on_escrow_sign)
            self.create_service(EscrowSubmitSignature, "escrow/submit_signature",
                                self._on_submit_signature)
            self.get_logger().info("escrow services ready")
            self._escrow_cb_group = ReentrantCallbackGroup()
            self._escrow_action = ActionServer(
                self, Escrow, "escrow", self._execute_escrow,
                callback_group=self._escrow_cb_group)


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
                # generate a key if the caller didn't supply one
                key = request.idempotency_key or f"auto-{uuid.uuid4()}"
                kwargs["idempotency_key"] = key
            result = self.backend.transfer(
                request.from_address, request.to_address,
                request.amount, request.asset or "USDC", **kwargs,
            )
            response.success = result["success"]
            response.tx_hash = result["tx_hash"]
            response.error = result["error"]
        except Exception as e:
            response.success = False
            response.error = str(e)
        return response

    def _on_escrow_sign(self, request, response):
        """Produce our signature for an escrow (local, free)."""
        try:
            eid = bytes.fromhex(request.escrow_id.removeprefix("0x"))
            if len(eid) != 32:
                raise ValueError(f"escrow_id must be 32 bytes (64 hex chars), got {len(eid)}")
            addr = request.signer_address or self.wallet.address()
            self.wallet.load(addr, self._passphrase)
            sig = self.escrow_backend.sign_release(eid, self.wallet.private_key())
            response.success = True
            response.signature = "0x" + sig.hex()
            response.signer = addr
            response.error = ""
        except Exception as e:
            response.success = False
            response.error = str(e)
        return response

    def _on_submit_signature(self, request, response):
        """Accept a signature from any transport into the store."""
        try:
            eid = bytes.fromhex(request.escrow_id.removeprefix("0x"))
            if len(eid) != 32:
                raise ValueError(f"escrow_id must be 32 bytes (64 hex chars), got {len(eid)}")
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

    def _execute_escrow(self, goal_handle):
        """Run one escrow: open, wait for both signatures, then release or refund."""
        goal = goal_handle.request
        result = Escrow.Result()
        feedback = Escrow.Feedback()

        def report(state: str, detail: str = ""):
            feedback.state = state
            feedback.detail = detail
            goal_handle.publish_feedback(feedback)
            self.get_logger().info(f"escrow: {state} {detail}")

        try:
            # ---- open ----
            report("opening")
            self.wallet.load(goal.from_address, self._passphrase)
            pk = self.wallet.private_key()
            terms = bytes.fromhex(goal.terms_hash.removeprefix("0x")) \
                if goal.terms_hash else bytes(32)

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
            deadline = opened["deadline"]
            report("locked", f"id=0x{eid.hex()} amount={goal.amount}")

            # ---- wait for both signatures, or the deadline ----
            report("awaiting_proof")
            announced_partial = False
            while True:
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    result.released = False
                    result.status = "cancelled"
                    return result

                sigs = self.signatures.get(eid)
                if len(sigs) == 1 and not announced_partial:
                    have = next(iter(sigs))
                    report("proof_partial", f"have {have}, waiting for the other")
                    announced_partial = True

                if self.signatures.has_both(eid):
                    report("releasing")
                    rel = self.escrow_backend.release_escrow(
                        eid, sigs["payer"], sigs["payee"], goal.from_address, pk)
                    self.signatures.clear(eid)
                    goal_handle.succeed()
                    result.released = True
                    result.status = "released"
                    result.tx_hash = "0x" + rel["tx_hash"]
                    return result

                if time.time() > deadline:
                    report("timed_out", "deadline passed, refunding")
                    report("refunding")
                    ref = self.escrow_backend.refund_escrow(eid, goal.from_address, pk)
                    self.signatures.clear(eid)
                    goal_handle.succeed()
                    result.released = False
                    result.status = "refunded_timeout"
                    result.tx_hash = "0x" + ref["tx_hash"]
                    return result

                time.sleep(1.0)

        except Exception as e:
            self.get_logger().error(f"escrow failed: {e}")
            goal_handle.abort()
            result.released = False
            result.status = "failed"
            result.error = str(e)
            return result


def main() -> None:
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
        rclpy.shutdown()


if __name__ == "__main__":
    main()