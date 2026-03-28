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
            'enable_sim_servo_bridge': LaunchConfiguration('enable_sim_servo_bridge'),
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
            'enable_sim_joint_bridge': LaunchConfiguration('enable_sim_joint_bridge'),
        }.items(),
    )

    return LaunchDescription([
        isaac_bridge_launch,
        sim_cpp_bridge_launch,
    ])
