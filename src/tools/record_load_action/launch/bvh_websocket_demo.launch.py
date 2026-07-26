"""Opt-in BVH WebSocket demo launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate the explicitly enabled BVH WebSocket demo stack."""
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用调试模式',
    )
    ws_host_arg = DeclareLaunchArgument(
        'ws_host',
        default_value='0.0.0.0',
        description='WebSocket服务器监听地址',
    )
    ws_port_arg = DeclareLaunchArgument(
        'ws_port',
        default_value='9105',
        description='WebSocket服务器监听端口',
    )
    device_id_arg = DeclareLaunchArgument(
        'device_id',
        default_value='robot',
        description='设备ID',
    )

    teleop_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('robot_bringup'),
                'launch',
                'teleop.launch.py',
            ])
        ),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
            'ws_host': LaunchConfiguration('ws_host'),
            'ws_port': LaunchConfiguration('ws_port'),
            'device_id': LaunchConfiguration('device_id'),
            'bridge_extension_factories': (
                'record_load_action.bvh_websocket_extension:create_extension'
            ),
            'execution_motion_command_topic': '/execution/motion/command',
        }.items(),
    )

    return LaunchDescription([
        debug_arg,
        ws_host_arg,
        ws_port_arg,
        device_id_arg,
        teleop_stack,
    ])
