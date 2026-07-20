"""ExecuteTask 到 ExecuteMotion 的正式 Action 边界桥。"""

from threading import Lock
from typing import Any, Optional

from action_msgs.msg import GoalStatus
from motion_msgs.action import ExecuteMotion
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from task_api_msgs.action import ExecuteTask

from .task_contract import (
    SingleGoalAdmission,
    map_motion_feedback,
    map_motion_result,
    map_task_goal,
    rejected_result,
    validate_task_goal,
)


class TaskServiceBridgeNode(Node):
    """只负责外部任务 Action 与内部运动 Action 的生命周期适配。"""

    def __init__(self) -> None:
        super().__init__('task_service_bridge')
        self.declare_parameter('task_action_name', '/task/execute')
        self.declare_parameter('motion_action_name', '/motion/execute')
        self.declare_parameter('motion_server_wait_timeout_sec', 5.0)

        task_action_name = self.get_parameter('task_action_name').value
        motion_action_name = self.get_parameter('motion_action_name').value
        self._motion_server_wait_timeout_sec = float(
            self.get_parameter('motion_server_wait_timeout_sec').value
        )

        self._callback_group = ReentrantCallbackGroup()
        self._admission = SingleGoalAdmission()
        self._state_lock = Lock()
        self._external_goal_handle: Optional[Any] = None
        self._motion_goal_handle: Optional[Any] = None

        self._motion_client = ActionClient(
            self,
            ExecuteMotion,
            motion_action_name,
            callback_group=self._callback_group,
        )
        self._task_server = ActionServer(
            self,
            ExecuteTask,
            task_action_name,
            execute_callback=self._execute_callback,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
            callback_group=self._callback_group,
        )

        self.get_logger().info(
            'task bridge ready: %s -> %s' % (
                task_action_name,
                motion_action_name,
            )
        )

    def _goal_callback(self, goal_request: ExecuteTask.Goal) -> GoalResponse:
        validation = validate_task_goal(goal_request)
        if not validation.accepted:
            self.get_logger().warning(
                'reject invalid task goal: %s' % validation.reason
            )
            return GoalResponse.REJECT
        if not self._admission.try_acquire():
            self.get_logger().warning('reject task goal: task_goal_active')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle: Any) -> CancelResponse:
        with self._state_lock:
            external_goal_handle = self._external_goal_handle
            motion_goal_handle = self._motion_goal_handle

        if not self._admission.occupied:
            return CancelResponse.REJECT
        if (
                external_goal_handle is not None
                and goal_handle is not external_goal_handle):
            return CancelResponse.REJECT
        if motion_goal_handle is not None:
            motion_goal_handle.cancel_goal_async()
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle: Any) -> ExecuteTask.Result:
        with self._state_lock:
            self._external_goal_handle = goal_handle

        try:
            if not self._motion_client.wait_for_server(
                    timeout_sec=self._motion_server_wait_timeout_sec):
                self._finish_failed_goal(goal_handle)
                return rejected_result(
                    ExecuteTask.Result,
                    'motion_action_unavailable',
                    goal_handle.request,
                )

            motion_goal = map_task_goal(
                goal_handle.request,
                ExecuteMotion.Goal,
            )
            send_goal_future = self._motion_client.send_goal_async(
                motion_goal,
                feedback_callback=lambda message: self._forward_feedback(
                    goal_handle,
                    message.feedback,
                ),
            )
            motion_goal_handle = await send_goal_future
            if not motion_goal_handle.accepted:
                self._finish_failed_goal(goal_handle)
                return rejected_result(
                    ExecuteTask.Result,
                    'motion_goal_rejected',
                    goal_handle.request,
                )

            with self._state_lock:
                self._motion_goal_handle = motion_goal_handle

            if goal_handle.is_cancel_requested:
                await motion_goal_handle.cancel_goal_async()

            result_response = await motion_goal_handle.get_result_async()
            task_result = map_motion_result(
                result_response.result,
                ExecuteTask.Result,
            )
            self._finish_external_goal(
                goal_handle,
                result_response.status,
                task_result.status,
            )
            return task_result
        except Exception as exc:  # noqa: BLE001 - Action 边界必须返回稳定结果
            self.get_logger().error('task bridge failed: %s' % exc)
            self._finish_failed_goal(goal_handle)
            return rejected_result(
                ExecuteTask.Result,
                'task_bridge_error',
                goal_handle.request,
            )
        finally:
            with self._state_lock:
                self._external_goal_handle = None
                self._motion_goal_handle = None
            self._admission.release()

    @staticmethod
    def _finish_external_goal(
            goal_handle: Any,
            motion_goal_status: int,
            result_status: str,
    ) -> None:
        if (
                goal_handle.is_cancel_requested
                or
                motion_goal_status == GoalStatus.STATUS_CANCELED
                or result_status == 'cancelled'):
            goal_handle.canceled()
        elif (
                motion_goal_status == GoalStatus.STATUS_SUCCEEDED
                and result_status == 'succeeded'):
            goal_handle.succeed()
        else:
            goal_handle.abort()

    @staticmethod
    def _finish_failed_goal(goal_handle: Any) -> None:
        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
        else:
            goal_handle.abort()

    @staticmethod
    def _forward_feedback(
            goal_handle: Any,
            motion_feedback: ExecuteMotion.Feedback,
    ) -> None:
        goal_handle.publish_feedback(
            map_motion_feedback(motion_feedback, ExecuteTask.Feedback)
        )

    def destroy_node(self) -> None:
        self._task_server.destroy()
        self._motion_client.destroy()
        super().destroy_node()


def main(args=None) -> None:
    """启动多线程执行器，避免嵌套 Action 回调互相等待。"""
    rclpy.init(args=args)
    node = TaskServiceBridgeNode()
    executor = MultiThreadedExecutor(num_threads=4)
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
