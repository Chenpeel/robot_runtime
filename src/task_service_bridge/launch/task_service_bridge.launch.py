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
        ],
    )

    return LaunchDescription([
        task_action_name_arg,
        motion_action_name_arg,
        motion_server_wait_timeout_sec_arg,
        node,
    ])
