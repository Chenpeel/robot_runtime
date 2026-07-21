"""正式任务 Action 边界桥独立启动文件。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    task_action_name_arg = DeclareLaunchArgument(
        'task_action_name',
        default_value='/task/execute',
        description='对外唯一正式任务 Action 名称',
    )
    motion_action_name_arg = DeclareLaunchArgument(
        'motion_action_name',
        default_value='/motion/execute',
        description='内部运动执行 Action 名称',
    )
    motion_server_wait_timeout_sec_arg = DeclareLaunchArgument(
        'motion_server_wait_timeout_sec',
        default_value='5.0',
        description='等待内部运动 Action Server 的最长秒数',
    )
    enable_context_arg = DeclareLaunchArgument(
        'enable_context',
        default_value='true',
        description='是否启用结构化语音/感知上下文订阅与发布',
    )
    speech_intent_topic_arg = DeclareLaunchArgument(
        'speech_intent_topic',
        default_value='/speech/intent',
        description='结构化语音意图输入话题',
    )
    perception_scene_topic_arg = DeclareLaunchArgument(
        'perception_scene_topic',
        default_value='/perception/scene_state',
        description='结构化感知场景输入话题',
    )
    task_context_topic_arg = DeclareLaunchArgument(
        'task_context_topic',
        default_value='/task/context_signal',
        description='面向外部任务服务的上下文事件话题',
    )

    node = Node(
        package='task_service_bridge',
        executable='task_service_bridge_node',
        name='task_service_bridge',
        output='screen',
        parameters=[
            {'task_action_name': LaunchConfiguration('task_action_name')},
            {'motion_action_name': LaunchConfiguration('motion_action_name')},
            {
                'motion_server_wait_timeout_sec': LaunchConfiguration(
                    'motion_server_wait_timeout_sec'
                )
            },
            {'enable_context': LaunchConfiguration('enable_context')},
            {'speech_intent_topic': LaunchConfiguration('speech_intent_topic')},
            {
                'perception_scene_topic': LaunchConfiguration(
                    'perception_scene_topic'
                )
            },
            {'task_context_topic': LaunchConfiguration('task_context_topic')},
        ],
    )

    return LaunchDescription([
        task_action_name_arg,
        motion_action_name_arg,
        motion_server_wait_timeout_sec_arg,
        enable_context_arg,
        speech_intent_topic_arg,
        perception_scene_topic_arg,
        task_context_topic_arg,
        node,
    ])
