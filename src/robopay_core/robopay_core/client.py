"""Convenience client for the escrow flow.
"""
from dataclasses import dataclass, field
from typing import Callable

from rclpy.action import ActionClient
from rclpy.node import Node

from robopay_interfaces.action import Escrow
from robopay_interfaces.srv import EscrowSign


@dataclass
class EscrowHandle:
    """A running escrow. `escrow_id` is populated once it's open on-chain."""
    escrow_id: str = ""
    state: str = "opening"
    detail: str = ""
    released: bool | None = None
    tx_hash: str = ""
    error: str = ""
    _goal_handle: object = field(default=None, repr=False)

    @property
    def is_open(self) -> bool:
        return bool(self.escrow_id) and self.released is None

    @property
    def is_finished(self) -> bool:
        return self.released is not None


class EscrowClient:
    def __init__(self, node: Node, action_name: str = "escrow",
                 sign_service: str = "escrow/sign") -> None:
        self._node = node
        self._action = ActionClient(node, Escrow, action_name)
        self._sign = node.create_client(EscrowSign, sign_service)


    def open(self, payer: str, payee: str, amount: str,
             timeout_seconds: float = 600.0, asset: str = "USDC",
             terms_hash: str = "", trust_level: int = 1,
             on_state: Callable[[EscrowHandle], None] | None = None,
             on_done: Callable[[EscrowHandle], None] | None = None,
             ) -> EscrowHandle:
        """Open an escrow. Returns immediately with a handle that fills in as
        the escrow progresses. `on_state` fires on every state change,
        `on_done` once when it releases or refunds."""
        handle = EscrowHandle()

        goal = Escrow.Goal()
        goal.from_address = payer
        goal.to_address = payee
        goal.amount = amount
        goal.asset = asset
        goal.terms_hash = terms_hash
        goal.trust_level = trust_level
        goal.timeout_seconds = float(timeout_seconds)

        def _feedback(msg):
            fb = msg.feedback
            handle.state = fb.state
            handle.detail = fb.detail
            if fb.escrow_id:
                handle.escrow_id = fb.escrow_id
            if on_state:
                on_state(handle)

        def _result(future):
            res = future.result().result
            handle.released = res.released
            handle.state = res.status
            handle.tx_hash = res.tx_hash
            handle.error = res.error
            if res.escrow_id:
                handle.escrow_id = res.escrow_id
            if on_done:
                on_done(handle)

        def _accepted(future):
            gh = future.result()
            if not gh.accepted:
                handle.state = "rejected"
                handle.released = False
                handle.error = "escrow goal rejected"
                if on_done:
                    on_done(handle)
                return
            handle._goal_handle = gh
            gh.get_result_async().add_done_callback(_result)

        if not self._action.server_is_ready():
            self._action.wait_for_server(timeout_sec=5.0)

        self._action.send_goal_async(
            goal, feedback_callback=_feedback).add_done_callback(_accepted)
        return handle

    def sign(self, escrow_id: str, role: str, signer_address: str = "",
             on_done: Callable[[bool, str], None] | None = None) -> None:
        """Sign our side of an escrow release. Non-blocking.

        The signature is published so the counterparty's node can collect it;
        the escrow releases once BOTH parties have signed.
        """
        if role not in ("payer", "payee"):
            raise ValueError(f"role must be 'payer' or 'payee', got {role!r}")

        request = EscrowSign.Request()
        request.escrow_id = escrow_id
        request.signer_address = signer_address
        request.role = role

        def _done(future):
            res = future.result()
            if on_done:
                on_done(res.success, res.error or res.signature)
            elif not res.success:
                self._node.get_logger().error(f"escrow sign failed: {res.error}")

        self._sign.call_async(request).add_done_callback(_done)


    def cancel(self, handle: EscrowHandle) -> None:
        """Cancel a running escrow (the funds refund at the deadline)."""
        if handle._goal_handle is not None:
            handle._goal_handle.cancel_goal_async()