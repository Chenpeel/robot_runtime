"""结构化语音与感知上下文场景。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    enable_speech_arg = DeclareLaunchArgument(
        'enable_speech_interface',
        default_value='true',
        description='是否启动结构化语音意图入口',
    )
    enable_perception_arg = DeclareLaunchArgument(
        'enable_vision_perception',
        default_value='true',
        description='是否启动结构化视觉场景入口',
    )
    speech_input_topic_arg = DeclareLaunchArgument(
        'speech_input_topic',
        default_value='/speech/intent_input',
        description='语音/NLU 边缘 JSON 输入话题',
    )
    speech_intent_topic_arg = DeclareLaunchArgument(
        'speech_intent_topic',
        default_value='/speech/intent',
        description='内部结构化语音意图话题',
    )
    perception_input_topic_arg = DeclareLaunchArgument(
        'perception_input_topic',
        default_value='/perception/detections_input',
        description='视觉后端边缘 JSON 输入话题',
    )
    perception_scene_topic_arg = DeclareLaunchArgument(
        'perception_scene_topic',
        default_value='/perception/scene_state',
        description='内部结构化场景状态话题',
    )
    task_action_name_arg = DeclareLaunchArgument(
        'task_action_name',
        default_value='/task/execute',
        description='语音意图必须使用的正式任务 Action',
    )
    task_server_wait_timeout_sec_arg = DeclareLaunchArgument(
        'task_server_wait_timeout_sec',
        default_value='2.0',
        description='语音入口等待正式任务 Action 的最长秒数',
    )
    speech_minimum_confidence_arg = DeclareLaunchArgument(
        'speech_minimum_confidence',
        default_value='0.6',
        description='允许发起正式任务的最低语音意图置信度',
    )

    speech_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('speech_interface'),
                'launch',
                'speech_interface.launch.py',
            ])
        ),
        condition=IfCondition(LaunchConfiguration('enable_speech_interface')),
        launch_arguments={
            'input_topic': LaunchConfiguration('speech_input_topic'),
            'intent_topic': LaunchConfiguration('speech_intent_topic'),
            'task_action_name': LaunchConfiguration('task_action_name'),
            'task_server_wait_timeout_sec': LaunchConfiguration(
                'task_server_wait_timeout_sec'
            ),
            'minimum_confidence': LaunchConfiguration(
                'speech_minimum_confidence'
            ),
        }.items(),
    )
    perception_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('vision_perception'),
                'launch',
                'vision_perception.launch.py',
            ])
        ),
        condition=IfCondition(LaunchConfiguration('enable_vision_perception')),
        launch_arguments={
            'input_topic': LaunchConfiguration('perception_input_topic'),
            'scene_topic': LaunchConfiguration('perception_scene_topic'),
        }.items(),
    )

    return LaunchDescription([
        enable_speech_arg,
        enable_perception_arg,
        speech_input_topic_arg,
        speech_intent_topic_arg,
        perception_input_topic_arg,
        perception_scene_topic_arg,
        task_action_name_arg,
        task_server_wait_timeout_sec_arg,
        speech_minimum_confidence_arg,
        speech_stack,
        perception_stack,
    ])
