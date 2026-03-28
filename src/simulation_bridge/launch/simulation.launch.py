"""Public simulation launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    enable_sim_servo_bridge_arg = DeclareLaunchArgument(
        'enable_sim_servo_bridge',
        default_value='true',
        description='是否启用 simulation 域的 servo 级桥接链路',
    )
    enable_sim_joint_bridge_arg = DeclareLaunchArgument(
        'enable_sim_joint_bridge',
        default_value='false',
        description='是否启用 simulation 域的 joint 级桥接链路',
    )
    simulation_bridge_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'bridge_stack.launch.py',
            ])
        ),
        launch_arguments={
            'enable_sim_servo_bridge': LaunchConfiguration('enable_sim_servo_bridge'),
            'enable_sim_joint_bridge': LaunchConfiguration('enable_sim_joint_bridge'),
        }.items(),
    )

    return LaunchDescription([
        enable_sim_servo_bridge_arg,
        enable_sim_joint_bridge_arg,
        simulation_bridge_stack,
    ])
