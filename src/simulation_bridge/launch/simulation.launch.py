"""Public simulation launch owned by simulation_bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    enable_isaac_bridge_arg = DeclareLaunchArgument(
        'enable_isaac_bridge',
        default_value='true',
        description='是否启动Isaac-ROS桥接节点',
    )
    enable_sim_cpp_bridge_arg = DeclareLaunchArgument(
        'enable_sim_cpp_bridge',
        default_value='false',
        description='是否启动C++仿真桥接节点(sim_servo_bridge_cpp)',
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

    simulation_bridge_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('simulation_bridge'),
                'launch',
                'bridge_stack.launch.py',
            ])
        ),
        launch_arguments={
            'enable_isaac_bridge': LaunchConfiguration('enable_isaac_bridge'),
            'enable_sim_cpp_bridge': LaunchConfiguration('enable_sim_cpp_bridge'),
            'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic'),
            'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic'),
            'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz'),
        }.items(),
    )

    return LaunchDescription([
        enable_isaac_bridge_arg,
        enable_sim_cpp_bridge_arg,
        sim_joint_cmd_topic_arg,
        sim_joint_state_fb_topic_arg,
        sim_publish_rate_hz_arg,
        simulation_bridge_stack,
    ])
