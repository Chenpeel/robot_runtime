"""视觉感知结构化输入节点启动文件。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    input_topic_arg = DeclareLaunchArgument(
        'input_topic',
        default_value='/perception/detections_input',
        description='感知边缘 JSON 输入话题',
    )
    scene_topic_arg = DeclareLaunchArgument(
        'scene_topic',
        default_value='/perception/scene_state',
        description='结构化场景状态输出话题',
    )
    node = Node(
        package='vision_perception',
        executable='vision_perception_node',
        name='vision_perception',
        output='screen',
        parameters=[
            {'input_topic': LaunchConfiguration('input_topic')},
            {'scene_topic': LaunchConfiguration('scene_topic')},
        ],
    )
    return LaunchDescription([input_topic_arg, scene_topic_arg, node])
