"""Servo-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DEFAULT_DRIVER_COMMAND_TOPIC = '/servo/command'
DEFAULT_DRIVER_STATE_TOPIC = '/servo/state'


def generate_launch_description():
    enable_sim_servo_bridge_arg = DeclareLaunchArgument(
        'enable_sim_servo_bridge',
        default_value='true',
        description='是否启用 simulation 域的 servo 级桥接链路',
    )
    isaac_bridge_debug_arg = DeclareLaunchArgument(
        'isaac_bridge_debug',
        default_value='false',
        description='Isaac-ROS桥接节点调试模式',
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
    isaac_enforce_limits_arg = DeclareLaunchArgument(
        'isaac_enforce_limits',
        default_value='true',
        description='Isaac桥接是否强制位置限幅',
    )

    isaac_bridge_node = Node(
        package='simulation_bridge',
        executable='isaac_bridge_node',
        name='isaac_ros_bridge',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_sim_servo_bridge')),
        parameters=[
            {'sim_servo_command_topic': LaunchConfiguration('sim_servo_command_topic')},
            {'sim_servo_state_topic': LaunchConfiguration('sim_servo_state_topic')},
            {'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC},
            {'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC},
            {'enforce_position_limits': LaunchConfiguration('isaac_enforce_limits')},
            {'debug': LaunchConfiguration('isaac_bridge_debug')},
        ],
    )

    return LaunchDescription([
        enable_sim_servo_bridge_arg,
        isaac_bridge_debug_arg,
        sim_servo_command_topic_arg,
        sim_servo_state_topic_arg,
        isaac_enforce_limits_arg,
        isaac_bridge_node,
    ])
