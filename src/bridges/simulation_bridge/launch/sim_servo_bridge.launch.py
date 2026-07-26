"""Servo-level simulation bridge launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

DEFAULT_PARAMS_FILE = PathJoinSubstitution([
    FindPackageShare('simulation_bridge'),
    'config',
    'default_params.yaml',
])


def generate_launch_description():
    sim_servo_bridge_node = Node(
        package='simulation_bridge',
        executable='sim_servo_bridge_node',
        name='sim_servo_bridge',
        output='screen',
        parameters=[
            DEFAULT_PARAMS_FILE,
        ],
    )

    return LaunchDescription([
        sim_servo_bridge_node,
    ])
