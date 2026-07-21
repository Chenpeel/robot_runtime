"""外部语音 JSON 到 SpeechIntent 和 ExecuteTask 的 ROS 适配节点。"""

from typing import Any, Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from speech_msgs.msg import SpeechIntent
from std_msgs.msg import String
from task_api_msgs.action import ExecuteTask

from .intent_contract import (
    IntentValidationError,
    SpeechIntentData,
    extract_speech_context,
    map_intent_to_task_goal,
    parse_speech_intent,
)


class SpeechInterfaceNode(Node):
    """严格验证外部语音意图，并只通过正式任务 Action 提交。"""

    def __init__(self) -> None:
        super().__init__('speech_interface')
        self.declare_parameter('input_topic', '/speech/intent_input')
        self.declare_parameter('intent_topic', '/speech/intent')
        self.declare_parameter('task_action_name', '/task/execute')
        self.declare_parameter('task_server_wait_timeout_sec', 2.0)
        self.declare_parameter('minimum_confidence', 0.6)

        input_topic = self.get_parameter('input_topic').value
        intent_topic = self.get_parameter('intent_topic').value
        task_action_name = self.get_parameter('task_action_name').value
        self._server_wait_timeout_sec = max(
            0.0,
            float(
                self.get_parameter(
                    'task_server_wait_timeout_sec'
                ).value
            ),
        )
        self._minimum_confidence = float(
            self.get_parameter('minimum_confidence').value
        )
        if not 0.0 <= self._minimum_confidence <= 1.0:
            raise ValueError('minimum_confidence must be within [0, 1]')

        self._callback_group = ReentrantCallbackGroup()
        self._intent_publisher = self.create_publisher(
            SpeechIntent,
            intent_topic,
            10,
        )
        self._task_client = ActionClient(
            self,
            ExecuteTask,
            task_action_name,
            callback_group=self._callback_group,
        )
        self._request_subscription = self.create_subscription(
            String,
            input_topic,
            self._request_callback,
            10,
            callback_group=self._callback_group,
        )

        self.get_logger().info(
            'speech interface ready: %s -> %s -> %s' % (
                input_topic,
                intent_topic,
                task_action_name,
            )
        )

    def _request_callback(self, message: String) -> None:
        try:
            intent = parse_speech_intent(
                message.data,
                minimum_confidence=self._minimum_confidence,
            )
        except IntentValidationError as exc:
            self._publish_status(
                extract_speech_context(message.data),
                status='rejected',
                reason=exc.reason,
                recoverable=True,
            )
            return

        self._publish_status(
            intent,
            status='accepted',
            reason='intent_valid',
            recoverable=False,
        )
        if not self._task_client.wait_for_server(
                timeout_sec=self._server_wait_timeout_sec):
            self._publish_status(
                intent,
                status='rejected',
                reason='task_action_unavailable',
                recoverable=True,
            )
            return

        task_goal = map_intent_to_task_goal(intent, ExecuteTask.Goal)
        try:
            goal_future = self._task_client.send_goal_async(task_goal)
            goal_future.add_done_callback(
                lambda future: self._goal_response_callback(intent, future)
            )
        except Exception as exc:  # noqa: BLE001 - ROS 边界统一为稳定状态
            self.get_logger().error('failed to send speech task: %s' % exc)
            self._publish_status(
                intent,
                status='failed',
                reason='task_goal_send_failed',
                recoverable=True,
            )

    def _goal_response_callback(self, intent: SpeechIntentData, future: Any) -> None:
        try:
            goal_handle = future.result()
        except Exception as exc:  # noqa: BLE001 - future 异常不得逃出回调
            self.get_logger().error('speech task goal response failed: %s' % exc)
            self._publish_status(
                intent,
                status='failed',
                reason='task_goal_response_failed',
                recoverable=True,
            )
            return

        if goal_handle is None or not goal_handle.accepted:
            self._publish_status(
                intent,
                status='rejected',
                reason='task_goal_rejected',
                recoverable=True,
            )
            return

        self._publish_status(
            intent,
            status='executing',
            reason='task_goal_accepted',
            recoverable=False,
        )
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda result: self._result_callback(intent, result)
        )

    def _result_callback(self, intent: SpeechIntentData, future: Any) -> None:
        try:
            response = future.result()
            result = response.result
            status = str(result.status or '').strip()
            reason = str(result.reason or '').strip()
            if not status:
                status = 'succeeded' if result.success else 'failed'
            if not reason:
                reason = 'task_result_without_reason'
            self._publish_status(
                intent,
                status=status,
                reason=reason,
                recoverable=bool(result.recoverable),
            )
        except Exception as exc:  # noqa: BLE001 - future 异常不得逃出回调
            self.get_logger().error('speech task result failed: %s' % exc)
            self._publish_status(
                intent,
                status='failed',
                reason='task_result_unavailable',
                recoverable=True,
            )

    def _publish_status(
            self,
            intent: Optional[Any],
            *,
            status: str,
            reason: str,
            recoverable: bool,
    ) -> None:
        message = SpeechIntent()
        message.stamp = self.get_clock().now().to_msg()
        if intent is not None:
            for field_name in (
                    'intent_id', 'task_id', 'trace_id', 'session_id',
                    'task_type', 'target_group', 'roll', 'pitch', 'yaw',
                    'duration_ms', 'position_tolerance',
                    'execution_timeout_sec', 'confidence'):
                value = getattr(intent, field_name, None)
                if value is not None:
                    setattr(message, field_name, value)
        message.status = status
        message.reason = reason
        message.recoverable = recoverable
        self._intent_publisher.publish(message)

    def destroy_node(self) -> None:
        self._task_client.destroy()
        super().destroy_node()


def main(args=None) -> None:
    """使用多线程执行器避免 Action future 与输入回调互相阻塞。"""
    rclpy.init(args=args)
    node = SpeechInterfaceNode()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
