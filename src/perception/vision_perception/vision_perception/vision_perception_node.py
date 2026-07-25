"""边缘 JSON 到结构化 SceneState 的 ROS 2 节点。"""

from typing import Optional

from perception_msgs.msg import DetectedObject, SceneState
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .scene_parser import ParseResult, parse_scene_json


DEFAULT_INPUT_TOPIC = '/perception/detections_input'
DEFAULT_SCENE_TOPIC = '/perception/scene_state'


class VisionPerceptionNode(Node):
    """只负责感知边缘输入校验和结构化场景发布。"""

    def __init__(self) -> None:
        super().__init__('vision_perception')
        self.declare_parameter('input_topic', DEFAULT_INPUT_TOPIC)
        self.declare_parameter('scene_topic', DEFAULT_SCENE_TOPIC)
        input_topic = str(self.get_parameter('input_topic').value)
        scene_topic = str(self.get_parameter('scene_topic').value)

        self.scene_pub = self.create_publisher(SceneState, scene_topic, 10)
        self.input_sub = self.create_subscription(
            String,
            input_topic,
            self._on_json,
            10,
        )
        self.get_logger().info(
            'vision perception ready: %s -> %s' % (input_topic, scene_topic)
        )

    def _on_json(self, message: String) -> None:
        result = parse_scene_json(message.data)
        self.scene_pub.publish(self._to_scene_state(result))

    def _to_scene_state(self, result: ParseResult) -> SceneState:
        message = SceneState()
        message.stamp = self.get_clock().now().to_msg()
        if not result.accepted or result.scene is None:
            if result.identity is not None:
                message.observation_id = result.identity.observation_id
                message.session_id = result.identity.session_id
                message.frame_id = result.identity.frame_id
            message.status = 'rejected'
            message.reason = result.reason or 'scene_rejected'
            message.recoverable = True
            return message

        scene = result.scene
        message.observation_id = scene.observation_id
        message.session_id = scene.session_id
        message.frame_id = scene.frame_id
        message.status = 'ok'
        message.reason = ''
        message.recoverable = False
        message.objects = [
            self._to_detected_object(item)
            for item in scene.objects
        ]
        return message

    @staticmethod
    def _to_detected_object(parsed_object) -> DetectedObject:
        message = DetectedObject()
        message.object_id = parsed_object.object_id
        message.label = parsed_object.label
        message.confidence = parsed_object.confidence
        message.x = parsed_object.x
        message.y = parsed_object.y
        message.z = parsed_object.z
        message.size_x = parsed_object.size_x
        message.size_y = parsed_object.size_y
        message.size_z = parsed_object.size_z
        return message


def main(args: Optional[list] = None) -> None:
    """启动感知结构化发布节点。"""
    rclpy.init(args=args)
    node = VisionPerceptionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
