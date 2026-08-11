"""Example: pay when a sensor condition becomes true.
Listens to a std_msgs/Bool topic and sends a USDC payment when it goes true.

A sensor topic publishing at 30Hz whose condition stays true for 2 seconds
delivers 60 messages. Without an EdgeTrigger you would send 60 payments.
The RateLimit is a second line of defence: even if a sensor misbehaves or the
predicate has a bug, it caps how much can leave the wallet.

Run it:
    ros2 run robopay_examples pay_on_condition --ros-args \\
        -p from_address:="'0xYourWallet'" \\
        -p to_address:="'0xTheirWallet'" \\
        -p amount:=0.01

Then trigger it by hand:
    ros2 topic pub --once /delivery_confirmed std_msgs/Bool "{data: true}"
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from robopay_interfaces.srv import Transfer

from robopay_core.triggers import EdgeTrigger, RateLimit


class PayOnCondition(Node):
    def __init__(self) -> None:
        super().__init__("pay_on_condition")

        self.declare_parameter("watch_topic", "/delivery_confirmed")
        self.declare_parameter("from_address", "")
        self.declare_parameter("to_address", "")
        self.declare_parameter("amount", "0.01")
        self.declare_parameter("max_payments_per_minute", 3)

        topic = self.get_parameter("watch_topic").value
        self.from_address = self.get_parameter("from_address").value
        self.to_address = self.get_parameter("to_address").value
        self.amount = str(self.get_parameter("amount").value)

        # fire once per false->true transition, not continuously
        self.trigger = EdgeTrigger()
        #hard ceiling on payments, whatever the sensor does
        self.limit = RateLimit(
            max_events=self.get_parameter("max_payments_per_minute").value,
            window_seconds=60,
        )

        self.pay_client = self.create_client(Transfer, "transfer/send")
        self.create_subscription(Bool, topic, self._on_sensor, 10)

        self.get_logger().info(
            f"watching {topic} - will pay {self.amount} USDC to "
            f"{self.to_address[:10]}... on a rising edge")

    def _on_sensor(self, msg: Bool) -> None:
        # 1. only act on the transition into true
        if not self.trigger.fired(msg.data):
            return

        # 2. respect the rate limit
        if not self.limit.allow():
            self.get_logger().warn(
                "condition fired but the rate limit blocked the payment")
            return

        self.get_logger().info("condition met - sending payment")
        self._send_payment()

    def _send_payment(self) -> None:
        if not self.pay_client.service_is_ready():
            self.get_logger().error("payment service unavailable - is payment_node running?")
            return

        request = Transfer.Request()
        request.from_address = self.from_address
        request.to_address = self.to_address
        request.amount = self.amount
        request.asset = "USDC"
        request.memo = "paid on sensor condition"

        # async so the sensor callback never blocks
        future = self.pay_client.call_async(request)
        future.add_done_callback(self._on_payment_result)

    def _on_payment_result(self, future) -> None:
        try:
            result = future.result()
            if result.success:
                self.get_logger().info(f"paid - tx 0x{result.tx_hash}")
            else:
                self.get_logger().error(f"payment failed: {result.error}")
        except Exception as e:
            self.get_logger().error(f"payment call raised: {e}")


def main() -> None:
    rclpy.init()
    node = PayOnCondition()
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