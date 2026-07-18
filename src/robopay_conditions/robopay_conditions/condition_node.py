"""robopay condition node (Phase 0 skeleton).

Phase 6 turns this into the predicate engine: subscribe to ROS topics, evaluate
predicates from config with a SAFE expression evaluator (simpleeval/asteval,
never eval()), and call the payment node when a condition fires.
"""
import rclpy
from rclpy.node import Node


class ConditionNode(Node):
    def __init__(self) -> None:
        super().__init__("condition_node")
        self.get_logger().info("robopay condition_node up (skeleton)")


def main() -> None:
    rclpy.init()
    node = ConditionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
