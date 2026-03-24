"""simulation bringup launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate simulation stack launch description."""
    enable_simulation_arg = DeclareLaunchArgument(
        'enable_simulation',
        default_value='true',
        description='是否启动simulation域桥接链路',
    )

    simulation_bridges = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'simulation_bridges.launch.py',
            ])
        ),
        condition=IfCondition(LaunchConfiguration('enable_simulation')),
    )

    log_info = LogInfo(
        msg=[
            '[robot_bringup/simulation] 仿真桥接链路已装配\n',
            '  仿真域启用: ',
            LaunchConfiguration('enable_simulation'),
            '\n',
        ],
    )

    return LaunchDescription([
        enable_simulation_arg,
        log_info,
        simulation_bridges,
    ])
