"""Joint-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

DEFAULT_PARAMS_FILE = PathJoinSubstitution([
    FindPackageShare('sim_joint_bridge_cpp'),
    'config',
    'default_params.yaml',
])


def generate_launch_description():
    sim_joint_bridge_debug_arg = DeclareLaunchArgument(
        'sim_joint_bridge_debug',
        default_value='false',
        description='仿真joint桥接节点调试模式',
    )

    sim_joint_bridge_node = Node(
        package='sim_joint_bridge_cpp',
        executable='sim_joint_bridge_node',
        name='sim_joint_bridge',
        output='screen',
        parameters=[
            DEFAULT_PARAMS_FILE,
            {'debug': LaunchConfiguration('sim_joint_bridge_debug')},
        ],
    )

    return LaunchDescription([
        sim_joint_bridge_debug_arg,
        sim_joint_bridge_node,
    ])
