"""execution_manager 独立启动文件。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    teleop_command_topic_arg = DeclareLaunchArgument(
        'teleop_command_topic',
        default_value='/execution/teleop/command',
        description='teleop 执行请求话题',
    )
    teleop_control_topic_arg = DeclareLaunchArgument(
        'teleop_control_topic',
        default_value='/execution/teleop/control',
        description='teleop 控制权话题',
    )
    motion_command_topic_arg = DeclareLaunchArgument(
        'motion_command_topic',
        default_value='/execution/motion/command',
        description='motion 执行请求话题',
    )
    output_command_topic_arg = DeclareLaunchArgument(
        'output_command_topic',
        default_value='/servo/command',
        description='驱动级舵机命令输出话题',
    )
    driver_state_topic_arg = DeclareLaunchArgument(
        'driver_state_topic',
        default_value='/servo/state',
        description='驱动级舵机状态输入话题',
    )
    actuator_state_topic_arg = DeclareLaunchArgument(
        'actuator_state_topic',
        default_value='/execution/actuator_state',
        description='执行层向上发布的执行器状态话题',
    )
    state_topic_arg = DeclareLaunchArgument(
        'state_topic',
        default_value='/execution/state',
        description='执行层状态话题',
    )
    estop_topic_arg = DeclareLaunchArgument(
        'estop_topic',
        default_value='/execution/estop',
        description='执行层急停控制话题',
    )
    teleop_timeout_sec_arg = DeclareLaunchArgument(
        'teleop_timeout_sec',
        default_value='0.8',
        description='teleop 控制权超时(秒)',
    )
    motion_timeout_sec_arg = DeclareLaunchArgument(
        'motion_timeout_sec',
        default_value='0.5',
        description='motion 控制权超时(秒)',
    )
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用 execution_manager 调试日志',
    )

    node = Node(
        package='execution_manager',
        executable='execution_manager_node',
        name='execution_manager',
        output='screen',
        parameters=[
            {'teleop_command_topic': LaunchConfiguration('teleop_command_topic')},
            {'teleop_control_topic': LaunchConfiguration('teleop_control_topic')},
            {'motion_command_topic': LaunchConfiguration('motion_command_topic')},
            {'output_command_topic': LaunchConfiguration('output_command_topic')},
            {'driver_state_topic': LaunchConfiguration('driver_state_topic')},
            {'actuator_state_topic': LaunchConfiguration('actuator_state_topic')},
            {'state_topic': LaunchConfiguration('state_topic')},
            {'estop_topic': LaunchConfiguration('estop_topic')},
            {'teleop_timeout_sec': LaunchConfiguration('teleop_timeout_sec')},
            {'motion_timeout_sec': LaunchConfiguration('motion_timeout_sec')},
            {'debug': LaunchConfiguration('debug')},
        ],
    )

    return LaunchDescription([
        teleop_command_topic_arg,
        teleop_control_topic_arg,
        motion_command_topic_arg,
        output_command_topic_arg,
        driver_state_topic_arg,
        actuator_state_topic_arg,
        state_topic_arg,
        estop_topic_arg,
        teleop_timeout_sec_arg,
        motion_timeout_sec_arg,
        debug_arg,
        node,
    ])
