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

    simulation_bridges = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'simulation_bridges.launch.py',
            ])
        ),
        condition=IfCondition(LaunchConfiguration('enable_simulation')),
        launch_arguments={
            'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic'),
            'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic'),
            'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz'),
        }.items(),
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
        sim_joint_cmd_topic_arg,
        sim_joint_state_fb_topic_arg,
        sim_publish_rate_hz_arg,
        log_info,
        simulation_bridges,
    ])
