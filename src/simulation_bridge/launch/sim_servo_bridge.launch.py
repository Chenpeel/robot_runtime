"""Servo-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

DEFAULT_PARAMS_FILE = PathJoinSubstitution([
    FindPackageShare('simulation_bridge'),
    'config',
    'default_params.yaml',
])


def generate_launch_description():
    sim_servo_bridge_debug_arg = DeclareLaunchArgument(
        'sim_servo_bridge_debug',
        default_value='false',
        description='仿真servo桥接节点调试模式',
    )
    sim_servo_command_topic_arg = DeclareLaunchArgument(
        'sim_servo_command_topic',
        default_value='/sim/servo_command',
        description='仿真侧舵机命令话题',
    )
    sim_servo_state_topic_arg = DeclareLaunchArgument(
        'sim_servo_state_topic',
        default_value='/sim/servo_state',
        description='仿真侧舵机状态话题',
    )
    sim_servo_enforce_limits_arg = DeclareLaunchArgument(
        'sim_servo_enforce_limits',
        default_value='true',
        description='仿真servo桥接是否强制位置限幅',
    )

    sim_servo_bridge_node = Node(
        package='simulation_bridge',
        executable='sim_servo_bridge_node',
        name='sim_servo_bridge',
        output='screen',
        parameters=[
            DEFAULT_PARAMS_FILE,
            {'sim_servo_command_topic': LaunchConfiguration('sim_servo_command_topic')},
            {'sim_servo_state_topic': LaunchConfiguration('sim_servo_state_topic')},
            {'enforce_position_limits': LaunchConfiguration('sim_servo_enforce_limits')},
            {'debug': LaunchConfiguration('sim_servo_bridge_debug')},
        ],
    )

    return LaunchDescription([
        sim_servo_bridge_debug_arg,
        sim_servo_command_topic_arg,
        sim_servo_state_topic_arg,
        sim_servo_enforce_limits_arg,
        sim_servo_bridge_node,
    ])
