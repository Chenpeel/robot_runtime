"""Joint-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

DEFAULT_PARAMS_FILE = PathJoinSubstitution([
    FindPackageShare('sim_joint_bridge_cpp'),
    'config',
    'default_params.yaml',
])


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
        package='sim_joint_bridge_cpp',
        executable='sim_joint_bridge_node',
        name='sim_joint_bridge',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_sim_joint_bridge')),
        parameters=[
            DEFAULT_PARAMS_FILE,
            {'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')},
            {'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')},
            {'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')},
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
