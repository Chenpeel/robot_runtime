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
    task_command_topic_arg = DeclareLaunchArgument(
        'task_command_topic',
        default_value='/execution/task/command',
        description='携带正式任务租约的执行请求话题',
    )
    task_control_topic_arg = DeclareLaunchArgument(
        'task_control_topic',
        default_value='/execution/task/control',
        description='正式任务执行租约控制话题',
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
    task_state_topic_arg = DeclareLaunchArgument(
        'task_state_topic',
        default_value='/execution/task/state',
        description='正式任务执行租约状态话题',
    )
    read_actuator_position_service_arg = DeclareLaunchArgument(
        'read_actuator_position_service',
        default_value='/execution/read_actuator_position',
        description='受 task lease 保护的实际执行器位置读取服务',
    )
    stop_actuators_service_arg = DeclareLaunchArgument(
        'stop_actuators_service',
        default_value='/execution/stop_actuators',
        description='受 task lease 保护的执行器停止请求服务',
    )
    driver_read_position_service_arg = DeclareLaunchArgument(
        'driver_read_position_service',
        default_value='/servo/read_position',
        description='驱动级位置读取服务',
    )
    driver_execute_command_service_arg = DeclareLaunchArgument(
        'driver_execute_command_service',
        default_value='/servo/execute_command',
        description='驱动级通用命令服务',
    )
    driver_safety_topic_arg = DeclareLaunchArgument(
        'driver_safety_topic',
        default_value='/servo/driver_safety',
        description='execution_manager 向驱动发布的权威安全锁存状态',
    )
    driver_safety_service_arg = DeclareLaunchArgument(
        'driver_safety_service',
        default_value='/servo/set_driver_safety',
        description='execution_manager 等待驱动安全状态应用确认的服务',
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
    task_timeout_sec_arg = DeclareLaunchArgument(
        'task_timeout_sec',
        default_value='5.0',
        description='正式任务执行租约超时(秒)',
    )
    driver_service_timeout_sec_arg = DeclareLaunchArgument(
        'driver_service_timeout_sec',
        default_value='2.0',
        description='执行层等待驱动级服务响应的最长秒数',
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
            {'task_command_topic': LaunchConfiguration('task_command_topic')},
            {'task_control_topic': LaunchConfiguration('task_control_topic')},
            {'motion_command_topic': LaunchConfiguration('motion_command_topic')},
            {'output_command_topic': LaunchConfiguration('output_command_topic')},
            {'driver_state_topic': LaunchConfiguration('driver_state_topic')},
            {'actuator_state_topic': LaunchConfiguration('actuator_state_topic')},
            {'state_topic': LaunchConfiguration('state_topic')},
            {'task_state_topic': LaunchConfiguration('task_state_topic')},
            {
                'read_actuator_position_service': LaunchConfiguration(
                    'read_actuator_position_service'
                )
            },
            {
                'stop_actuators_service': LaunchConfiguration(
                    'stop_actuators_service'
                )
            },
            {
                'driver_read_position_service': LaunchConfiguration(
                    'driver_read_position_service'
                )
            },
            {
                'driver_execute_command_service': LaunchConfiguration(
                    'driver_execute_command_service'
                )
            },
            {'driver_safety_topic': LaunchConfiguration('driver_safety_topic')},
            {'driver_safety_service': LaunchConfiguration('driver_safety_service')},
            {'estop_topic': LaunchConfiguration('estop_topic')},
            {'teleop_timeout_sec': LaunchConfiguration('teleop_timeout_sec')},
            {'motion_timeout_sec': LaunchConfiguration('motion_timeout_sec')},
            {'task_timeout_sec': LaunchConfiguration('task_timeout_sec')},
            {
                'driver_service_timeout_sec': LaunchConfiguration(
                    'driver_service_timeout_sec'
                )
            },
            {'debug': LaunchConfiguration('debug')},
        ],
    )

    return LaunchDescription([
        teleop_command_topic_arg,
        teleop_control_topic_arg,
        task_command_topic_arg,
        task_control_topic_arg,
        motion_command_topic_arg,
        output_command_topic_arg,
        driver_state_topic_arg,
        actuator_state_topic_arg,
        state_topic_arg,
        task_state_topic_arg,
        read_actuator_position_service_arg,
        stop_actuators_service_arg,
        driver_read_position_service_arg,
        driver_execute_command_service_arg,
        driver_safety_topic_arg,
        driver_safety_service_arg,
        estop_topic_arg,
        teleop_timeout_sec_arg,
        motion_timeout_sec_arg,
        task_timeout_sec_arg,
        driver_service_timeout_sec_arg,
        debug_arg,
        node,
    ])
