"""Public simulation launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    sim_servo_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'sim_servo_bridge.launch.py',
            ])
        ),
    )
    sim_joint_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'sim_joint_bridge.launch.py',
            ])
        ),
    )

    return LaunchDescription([
        sim_servo_bridge_launch,
        sim_joint_bridge_launch,
    ])
