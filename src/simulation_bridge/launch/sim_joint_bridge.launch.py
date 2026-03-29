"""Joint-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DEFAULT_DRIVER_COMMAND_TOPIC = '/servo/command'
DEFAULT_DRIVER_STATE_TOPIC = '/servo/state'


def generate_launch_description():
    enable_sim_joint_bridge_arg = DeclareLaunchArgument(
        'enable_sim_joint_bridge',
        default_value='false',
        description='是否启用 simulation 域的 joint 级桥接链路',
    )
    sim_joint_bridge_debug_arg = DeclareLaunchArgument(
        'sim_joint_bridge_debug',
        default_value='false',
        description='仿真joint桥接节点调试模式',
    )
    sim_joint_cmd_topic_arg = DeclareLaunchArgument(
        'sim_joint_cmd_topic',
        default_value='/sim/joint_cmd',
        description='仿真侧关节命令话题(std_msgs/Float32MultiArray)',
    )
    sim_joint_state_fb_topic_arg = DeclareLaunchArgument(
        'sim_joint_state_fb_topic',
        default_value='/sim/joint_state_fb',
        description='仿真侧关节反馈话题(std_msgs/Float32MultiArray)',
    )
    sim_publish_rate_hz_arg = DeclareLaunchArgument(
        'sim_publish_rate_hz',
        default_value='50.0',
        description='C++仿真桥接发布频率(Hz)',
    )

    sim_joint_bridge_node = Node(
        package='sim_servo_bridge_cpp',
        executable='sim_servo_bridge_node',
        name='sim_servo_bridge',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_sim_joint_bridge')),
        parameters=[
            {'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')},
            {'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')},
            {'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC},
            {'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC},
            {'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')},
            {'speed': 100},
            {'debug': LaunchConfiguration('sim_joint_bridge_debug')},
        ],
    )

    return LaunchDescription([
        enable_sim_joint_bridge_arg,
        sim_joint_bridge_debug_arg,
        sim_joint_cmd_topic_arg,
        sim_joint_state_fb_topic_arg,
        sim_publish_rate_hz_arg,
        sim_joint_bridge_node,
    ])
