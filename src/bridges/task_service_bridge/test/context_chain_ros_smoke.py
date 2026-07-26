"""Phase 5 语音/感知到正式任务上下文的 ROS 2 smoke。"""

import json
import threading
import time

from motion_msgs.action import ExecuteMotion
from perception_msgs.msg import SceneState
import rclpy
from rclpy.action import ActionServer
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from speech_interface.speech_interface_node import SpeechInterfaceNode
from speech_msgs.msg import SpeechIntent
from std_msgs.msg import String
from task_api_msgs.msg import TaskContextSignal
from task_service_bridge.bridge_node import TaskServiceBridgeNode
from vision_perception.vision_perception_node import VisionPerceptionNode


TIMEOUT_SEC = 12.0


class FakeMotionNode(Node):
    """只验证 task bridge 生命周期映射，不模拟驱动完成语义。"""

    def __init__(self) -> None:
        super().__init__('phase5_fake_motion')
        self.last_request = None
        self.server = ActionServer(
            self,
            ExecuteMotion,
            '/motion/execute',
            execute_callback=self._execute,
        )

    async def _execute(self, goal_handle):
        request = goal_handle.request
        self.last_request = request
        result = ExecuteMotion.Result()
        result.success = True
        result.task_id = request.task_id
        result.trace_id = request.trace_id
        result.session_id = request.session_id
        result.status = 'succeeded'
        result.reason = 'phase5_fake_motion_complete'
        result.recoverable = False
        result.target_reached = True
        result.admission_released = True
        result.stop_requested = False
        result.stop_command_sent = False
        result.stop_confirmed = False
        goal_handle.succeed()
        return result

    def destroy_node(self) -> None:
        self.server.destroy()
        super().destroy_node()


class ProbeNode(Node):
    """发布两类边缘输入并观察全部结构化边界。"""

    def __init__(self) -> None:
        super().__init__('phase5_context_probe')
        self.speech_statuses = []
        self.scenes = []
        self.contexts = []
        self.speech_input = self.create_publisher(
            String,
            '/speech/intent_input',
            10,
        )
        self.perception_input = self.create_publisher(
            String,
            '/perception/detections_input',
            10,
        )
        self.create_subscription(
            SpeechIntent,
            '/speech/intent',
            self.speech_statuses.append,
            20,
        )
        self.create_subscription(
            SceneState,
            '/perception/scene_state',
            self.scenes.append,
            20,
        )
        self.create_subscription(
            TaskContextSignal,
            '/task/context_signal',
            self.contexts.append,
            20,
        )

    def publish_json(self, publisher, document) -> None:
        message = String()
        message.data = json.dumps(document, allow_nan=False)
        publisher.publish(message)


def _speech_document(confidence=0.95):
    return {
        'intent_id': 'intent-phase5',
        'task_id': 'task-phase5',
        'trace_id': 'trace-phase5',
        'session_id': 'session-phase5',
        'task_type': 'ankle_pose',
        'target_group': 'right_ankle',
        'roll': 1.0,
        'pitch': -2.0,
        'yaw': 3.0,
        'duration_ms': 100,
        'position_tolerance': 10,
        'execution_timeout_sec': 5.0,
        'confidence': confidence,
    }


def _scene_document(duplicate=False):
    objects = [
        {
            'object_id': 'object-1',
            'label': 'cup',
            'confidence': 0.9,
            'x': 1.0,
            'y': 2.0,
            'z': 3.0,
            'size_x': 0.1,
            'size_y': 0.2,
            'size_z': 0.3,
        },
    ]
    if duplicate:
        objects.append(dict(objects[0]))
    return {
        'observation_id': 'observation-phase5',
        'session_id': 'session-phase5',
        'frame_id': 'camera_link',
        'objects': objects,
    }


def _wait_for(predicate, timeout_sec=TIMEOUT_SEC):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def run_scenario():
    started_at = time.monotonic()
    rclpy.init()
    nodes = [
        FakeMotionNode(),
        TaskServiceBridgeNode(),
        SpeechInterfaceNode(),
        VisionPerceptionNode(),
        ProbeNode(),
    ]
    fake_motion, _, _, _, probe = nodes
    executor = MultiThreadedExecutor(num_threads=8)
    for node in nodes:
        executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        if not _wait_for(
                lambda: probe.speech_input.get_subscription_count() == 1
                and probe.perception_input.get_subscription_count() == 1):
            raise RuntimeError('phase5_input_discovery_timeout')

        probe.publish_json(probe.speech_input, _speech_document())
        probe.publish_json(probe.perception_input, _scene_document())
        if not _wait_for(lambda: (
                fake_motion.last_request is not None
                and any(item.status == 'succeeded'
                        for item in probe.speech_statuses)
                and any(item.status == 'ok' for item in probe.scenes)
                and any(item.source == 'speech'
                        and item.status == 'succeeded'
                        for item in probe.contexts)
                and any(item.source == 'perception'
                        and item.status == 'ok'
                        for item in probe.contexts)
        )):
            raise RuntimeError('phase5_success_chain_timeout')

        probe.publish_json(
            probe.speech_input,
            _speech_document(confidence=0.1),
        )
        probe.publish_json(
            probe.perception_input,
            _scene_document(duplicate=True),
        )
        if not _wait_for(lambda: (
                any(item.status == 'rejected'
                    and item.reason == 'confidence_below_minimum'
                    and item.intent_id == 'intent-phase5'
                    and item.session_id == 'session-phase5'
                    for item in probe.speech_statuses)
                and any(item.status == 'rejected'
                        and item.reason == 'object_id_not_unique'
                        and item.observation_id == 'observation-phase5'
                        and item.session_id == 'session-phase5'
                        for item in probe.scenes)
                and any(item.source == 'speech'
                        and item.reason == 'confidence_below_minimum'
                        and item.event_id == 'intent-phase5'
                        and item.session_id == 'session-phase5'
                        for item in probe.contexts)
                and any(item.source == 'perception'
                        and item.reason == 'object_id_not_unique'
                        and item.event_id == 'observation-phase5'
                        and item.session_id == 'session-phase5'
                        for item in probe.contexts)
        )):
            raise RuntimeError('phase5_rejection_chain_timeout')

        motion_request = fake_motion.last_request
        perception_context = next(
            item for item in probe.contexts
            if item.source == 'perception' and item.status == 'ok'
        )
        return {
            'elapsed_sec': time.monotonic() - started_at,
            'motion_task_id': motion_request.task_id,
            'motion_trace_id': motion_request.trace_id,
            'motion_session_id': motion_request.session_id,
            'speech_succeeded': True,
            'speech_rejected': True,
            'perception_ready': True,
            'perception_rejected': True,
            'perception_labels': list(perception_context.labels),
        }
    finally:
        executor.shutdown()
        spin_thread.join(timeout=2.0)
        for node in reversed(nodes):
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    print(json.dumps(run_scenario(), sort_keys=True))
