"""Internal bridge stack launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    isaac_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'isaac_bridge.launch.py',
            ])
        ),
        launch_arguments={
            'enable_isaac_bridge': LaunchConfiguration('enable_isaac_bridge'),
            'isaac_bridge_debug': LaunchConfiguration('isaac_bridge_debug'),
            'isaac_command_topic': LaunchConfiguration('isaac_command_topic'),
            'isaac_state_topic': LaunchConfiguration('isaac_state_topic'),
            'isaac_enforce_limits': LaunchConfiguration('isaac_enforce_limits'),
        }.items(),
    )

    sim_cpp_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'sim_cpp_bridge.launch.py',
            ])
        ),
        launch_arguments={
            'enable_sim_cpp_bridge': LaunchConfiguration('enable_sim_cpp_bridge'),
            'sim_cpp_bridge_debug': LaunchConfiguration('sim_cpp_bridge_debug'),
            'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic'),
            'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic'),
            'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz'),
        }.items(),
    )

    return LaunchDescription([
        isaac_bridge_launch,
        sim_cpp_bridge_launch,
    ])
