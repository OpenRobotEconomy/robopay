"""Example: escrow a payment, release it when a sensor confirms delivery."""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from robopay_core.client import EscrowClient
from robopay_core.triggers import EdgeTrigger


class EscrowOnDelivery(Node):
    def __init__(self) -> None:
        super().__init__("escrow_on_delivery")

        self.declare_parameter("payer", "")
        self.declare_parameter("payee", "")
        self.declare_parameter("amount", "0.05")
        self.payer = self.get_parameter("payer").value

        self.trigger = EdgeTrigger()
        self.escrow = EscrowClient(self)

        # lock the payment up front
        self.escrow_handle = self.escrow.open(
            payer=self.payer,
            payee=self.get_parameter("payee").value,
            amount=self.get_parameter("amount").value,
            timeout_seconds=600,
            on_state=lambda h: self.get_logger().info(f"escrow: {h.state} {h.detail} {h.escrow_id}"),
            on_done=self._finished,
        )

        self.create_subscription(Bool, "/delivery_confirmed", self._on_delivery, 10)

    def _on_delivery(self, msg: Bool) -> None:
        if not self.trigger.fired(msg.data) or not self.escrow_handle.is_open:
            return
        self.get_logger().info("delivery confirmed - signing release")
        self.escrow.sign(self.escrow_handle.escrow_id, role="payer",
                         signer_address=self.payer)

    def _finished(self, handle) -> None:
        if handle.released:
            self.get_logger().info(f"released - tx {handle.tx_hash}")
        else:
            self.get_logger().warn(f"not released: {handle.state} {handle.error}")


def main() -> None:
    rclpy.init()
    node = EscrowOnDelivery()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()