"""execution_manager ROS 2 节点。"""

from motion_msgs.msg import ExecutionState
from motion_msgs.msg import MotionCommand
from motion_msgs.msg import TeleopControl
import rclpy
from rclpy.node import Node
from servo_msgs.msg import ServoCommand
from std_msgs.msg import Bool

from .arbitrator import CommandArbitrator
from .arbitrator import CommandFrame


class ExecutionManagerNode(Node):
    """最小执行仲裁节点。"""

    def __init__(self) -> None:
        super().__init__('execution_manager')

        self.declare_parameter('teleop_command_topic', '/execution/teleop/command')
        self.declare_parameter('teleop_control_topic', '/execution/teleop/control')
        self.declare_parameter('motion_command_topic', '/execution/motion/command')
        self.declare_parameter('output_command_topic', '/servo/command')
        self.declare_parameter('state_topic', '/execution/state')
        self.declare_parameter('estop_topic', '/execution/estop')
        self.declare_parameter('teleop_timeout_sec', 0.8)
        self.declare_parameter('motion_timeout_sec', 0.5)
        self.declare_parameter('publish_state_period_sec', 0.2)
        self.declare_parameter('debug', False)

        teleop_command_topic = self.get_parameter('teleop_command_topic').value
        teleop_control_topic = self.get_parameter('teleop_control_topic').value
        motion_command_topic = self.get_parameter('motion_command_topic').value
        output_command_topic = self.get_parameter('output_command_topic').value
        self.state_topic = self.get_parameter('state_topic').value
        estop_topic = self.get_parameter('estop_topic').value
        teleop_timeout_sec = float(self.get_parameter('teleop_timeout_sec').value)
        motion_timeout_sec = float(self.get_parameter('motion_timeout_sec').value)
        publish_state_period_sec = float(
            self.get_parameter('publish_state_period_sec').value
        )
        self.debug = bool(self.get_parameter('debug').value)

        self.arbitrator = CommandArbitrator(
            teleop_timeout_sec=teleop_timeout_sec,
            motion_timeout_sec=motion_timeout_sec,
        )

        self.output_command_pub = self.create_publisher(
            ServoCommand,
            output_command_topic,
            50,
        )
        self.state_pub = self.create_publisher(
            ExecutionState,
            self.state_topic,
            10,
        )

        self.teleop_sub = self.create_subscription(
            MotionCommand,
            teleop_command_topic,
            lambda msg: self._handle_command('teleop', msg),
            50,
        )
        self.teleop_control_sub = self.create_subscription(
            TeleopControl,
            teleop_control_topic,
            self._handle_teleop_control,
            20,
        )
        self.motion_sub = self.create_subscription(
            MotionCommand,
            motion_command_topic,
            lambda msg: self._handle_command('motion', msg),
            50,
        )
        self.estop_sub = self.create_subscription(
            Bool,
            estop_topic,
            self._handle_estop,
            10,
        )

        period = publish_state_period_sec if publish_state_period_sec > 0 else 0.2
        self.state_timer = self.create_timer(period, self._publish_state)

        self.get_logger().info(
            'execution_manager 已启动: '
            f'teleop={teleop_command_topic}, '
            f'teleop_control={teleop_control_topic}, '
            f'motion={motion_command_topic}, '
            f'output={output_command_topic}, '
            f'estop={estop_topic}'
        )

    def _handle_command(self, source: str, msg: MotionCommand) -> None:
        now_sec = self._now_sec()
        frame = CommandFrame(
            servo_type=str(msg.servo_type),
            servo_id=int(msg.servo_id),
            position=int(msg.position),
            speed=int(msg.speed),
        )
        result = self.arbitrator.receive_command(source, frame, now_sec)
        if result.accepted:
            self.output_command_pub.publish(self._to_servo_command(msg))
            if self.debug:
                self.get_logger().info(
                    f'接受 {source} 命令: type={msg.servo_type} '
                    f'id={msg.servo_id} pos={msg.position} speed={msg.speed}'
                )
        else:
            self.get_logger().warn(
                f'拒绝 {source} 命令: reason={result.reason} '
                f'id={msg.servo_id} pos={msg.position}'
            )

        self._publish_state(now_sec)

    def _handle_teleop_control(self, msg: TeleopControl) -> None:
        now_sec = self._now_sec()
        action = str(msg.action).strip().lower()
        result = self.arbitrator.receive_teleop_control(action, now_sec)

        if self.debug:
            self.get_logger().info(
                f'teleop 控制动作: action={action} '
                f'accepted={result.accepted} mode={result.mode}'
            )

        if not result.accepted:
            self.get_logger().warn(
                f'拒绝 teleop 控制动作: action={action} reason={result.reason}'
            )

        self._publish_state(now_sec)

    def _handle_estop(self, msg: Bool) -> None:
        state = self.arbitrator.set_estop(bool(msg.data), self._now_sec())
        self.get_logger().warn(
            f'执行层急停状态已切换: estop_active={state["estop_active"]}'
        )
        self._publish_state()

    def _publish_state(self, now_sec: float | None = None) -> None:
        if now_sec is None:
            now_sec = self._now_sec()

        snapshot = self.arbitrator.snapshot(now_sec)
        state_msg = ExecutionState()
        state_msg.mode = str(snapshot['mode'])
        state_msg.active_source = str(snapshot['active_source'] or '')
        state_msg.estop_active = bool(snapshot['estop_active'])
        state_msg.teleop_active = bool(snapshot['teleop_active'])
        state_msg.motion_active = bool(snapshot['motion_active'])
        state_msg.teleop_timeout_sec = float(snapshot['teleop_timeout_sec'])
        state_msg.motion_timeout_sec = float(snapshot['motion_timeout_sec'])
        state_msg.teleop_accepted_count = int(snapshot['accepted_counts']['teleop'])
        state_msg.motion_accepted_count = int(snapshot['accepted_counts']['motion'])
        state_msg.teleop_rejected_count = int(snapshot['rejected_counts']['teleop'])
        state_msg.motion_rejected_count = int(snapshot['rejected_counts']['motion'])
        state_msg.last_rejection_reason = str(snapshot['last_rejection_reason'])
        state_msg.stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(state_msg)

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    @staticmethod
    def _to_servo_command(msg: MotionCommand) -> ServoCommand:
        output_msg = ServoCommand()
        output_msg.servo_type = str(msg.servo_type)
        output_msg.servo_id = int(msg.servo_id)
        output_msg.position = int(msg.position)
        output_msg.speed = int(msg.speed)
        output_msg.stamp = msg.stamp
        return output_msg


def main(args=None) -> None:
    """入口函数。"""
    rclpy.init(args=args)
    node = ExecutionManagerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
