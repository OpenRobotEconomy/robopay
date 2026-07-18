"""robopay payment node (Phase 0 skeleton).

Holds the wallet provider and settlement backend, and exposes services wired to
the in-memory MockBackend so the flow runs with no chain and no money. The
self-custody backend (default) and Circle backend (opt-in) implement the same
interfaces and slot in over later phases.
"""
import rclpy
from rclpy.node import Node

from robopay_interfaces.srv import Transfer, WalletBalance, WalletCreate

from robopay_core.backends.mock import MockBackend
from robopay_core.wallets.self_custody import SelfCustodyProvider


class PaymentNode(Node):
    def __init__(self) -> None:
        super().__init__("payment_node")
        self.backend = MockBackend()
        self.wallet = SelfCustodyProvider()
        self.create_service(WalletCreate, "wallet/create", self._on_wallet_create)
        self.create_service(WalletBalance, "wallet/balance", self._on_wallet_balance)
        self.create_service(Transfer, "transfer/send", self._on_transfer)
        self.get_logger().info("robopay payment_node up (mock backend, self-custody wallet)")

    def _on_wallet_create(self, request, response):
        addr = self.wallet.create(request.label or "robot")
        self.backend.fund(addr, 100.0)  # seed test USDC so demos work
        response.success = True
        response.address = addr
        return response

    def _on_wallet_balance(self, request, response):
        bal = self.backend.balance(request.address)
        response.success = True
        response.usdc = str(bal.get("USDC", 0.0))
        response.gas = "0"
        response.error = ""
        return response

    def _on_transfer(self, request, response):
        result = self.backend.transfer(
            request.from_address, request.to_address,
            request.amount, request.asset or "USDC",
        )
        response.success = result["success"]
        response.tx_hash = result["tx_hash"]
        response.error = result["error"]
        return response


def main() -> None:
    rclpy.init()
    node = PaymentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
