"""speech_interface 独立启动入口。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    input_topic_arg = DeclareLaunchArgument(
        'input_topic',
        default_value='/speech/intent_input',
        description='外部语音 JSON 输入话题',
    )
    intent_topic_arg = DeclareLaunchArgument(
        'intent_topic',
        default_value='/speech/intent',
        description='结构化语音意图及状态更新话题',
    )
    task_action_name_arg = DeclareLaunchArgument(
        'task_action_name',
        default_value='/task/execute',
        description='唯一正式任务 Action 名称',
    )
    task_server_wait_timeout_sec_arg = DeclareLaunchArgument(
        'task_server_wait_timeout_sec',
        default_value='2.0',
        description='等待正式任务 Action Server 的最长秒数',
    )
    minimum_confidence_arg = DeclareLaunchArgument(
        'minimum_confidence',
        default_value='0.6',
        description='允许提交正式任务的最低语音意图置信度',
    )

    node = Node(
        package='speech_interface',
        executable='speech_interface_node',
        name='speech_interface',
        output='screen',
        parameters=[
            {'input_topic': LaunchConfiguration('input_topic')},
            {'intent_topic': LaunchConfiguration('intent_topic')},
            {'task_action_name': LaunchConfiguration('task_action_name')},
            {
                'task_server_wait_timeout_sec': LaunchConfiguration(
                    'task_server_wait_timeout_sec'
                )
            },
            {
                'minimum_confidence': LaunchConfiguration(
                    'minimum_confidence'
                )
            },
        ],
    )

    return LaunchDescription([
        input_topic_arg,
        intent_topic_arg,
        task_action_name_arg,
        task_server_wait_timeout_sec_arg,
        minimum_confidence_arg,
        node,
    ])
