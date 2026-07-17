"""teleop bringup launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate teleop stack launch description."""
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用调试模式',
    )
    ws_host_arg = DeclareLaunchArgument(
        'ws_host',
        default_value='0.0.0.0',
        description='WebSocket服务器监听地址',
    )
    ws_port_arg = DeclareLaunchArgument(
        'ws_port',
        default_value='9105',
        description='WebSocket服务器监听端口',
    )
    device_id_arg = DeclareLaunchArgument(
        'device_id',
        default_value='robot',
        description='设备ID',
    )
    enable_execution_manager_arg = DeclareLaunchArgument(
        'enable_execution_manager',
        default_value='true',
        description='是否启动执行仲裁节点',
    )
    execution_teleop_command_topic_arg = DeclareLaunchArgument(
        'execution_teleop_command_topic',
        default_value='/execution/teleop/command',
        description='teleop 执行请求话题',
    )
    execution_teleop_control_topic_arg = DeclareLaunchArgument(
        'execution_teleop_control_topic',
        default_value='/execution/teleop/control',
        description='teleop 控制权话题',
    )
    execution_motion_command_topic_arg = DeclareLaunchArgument(
        'execution_motion_command_topic',
        default_value='/execution/motion/command',
        description='motion 执行请求话题',
    )
    execution_state_topic_arg = DeclareLaunchArgument(
        'execution_state_topic',
        default_value='/execution/state',
        description='执行层状态话题',
    )
    execution_estop_topic_arg = DeclareLaunchArgument(
        'execution_estop_topic',
        default_value='/execution/estop',
        description='执行层急停控制话题',
    )
    execution_teleop_timeout_sec_arg = DeclareLaunchArgument(
        'execution_teleop_timeout_sec',
        default_value='0.8',
        description='teleop 控制权超时(秒)',
    )
    execution_motion_timeout_sec_arg = DeclareLaunchArgument(
        'execution_motion_timeout_sec',
        default_value='0.5',
        description='motion 控制权超时(秒)',
    )
    execution_debug_arg = DeclareLaunchArgument(
        'execution_debug',
        default_value=LaunchConfiguration('debug'),
        description='执行仲裁节点调试模式',
    )
    bridge_debug_arg = DeclareLaunchArgument(
        'bridge_debug',
        default_value=LaunchConfiguration('debug'),
        description='WebSocket桥接节点调试模式',
    )
    bridge_extension_factories_arg = DeclareLaunchArgument(
        'bridge_extension_factories',
        default_value='',
        description='WebSocket桥接可选扩展工厂（逗号分隔）',
    )
    imu_debug_arg = DeclareLaunchArgument(
        'imu_debug',
        default_value='false',
        description='IMU 是否启用调试模式',
    )
    heartbeat_debug_arg = DeclareLaunchArgument(
        'heartbeat_debug',
        default_value='false',
        description='心跳调试模式',
    )
    ws_debug_arg = DeclareLaunchArgument(
        'ws_debug',
        default_value='false',
        description='WebSocket服务端调试模式',
    )
    debug_aggregate_arg = DeclareLaunchArgument(
        'debug_aggregate',
        default_value='true',
        description='是否聚合调试日志',
    )
    debug_aggregate_period_arg = DeclareLaunchArgument(
        'debug_aggregate_period',
        default_value='1.0',
        description='调试日志聚合刷新周期(秒)',
    )
    debug_aggregate_max_len_arg = DeclareLaunchArgument(
        'debug_aggregate_max_len',
        default_value='120',
        description='调试日志聚合单条最大长度',
    )
    execution_teleop_command_topic = LaunchConfiguration('execution_teleop_command_topic')
    execution_teleop_control_topic = LaunchConfiguration('execution_teleop_control_topic')
    execution_motion_command_topic = LaunchConfiguration('execution_motion_command_topic')
    execution_state_topic = LaunchConfiguration('execution_state_topic')
    execution_estop_topic = LaunchConfiguration('execution_estop_topic')

    execution_manager_node = Node(
        package='execution_manager',
        executable='execution_manager_node',
        name='execution_manager',
        output='screen',
        condition=IfCondition(LaunchConfiguration('enable_execution_manager')),
        parameters=[
            {'teleop_command_topic': execution_teleop_command_topic},
            {'teleop_control_topic': execution_teleop_control_topic},
            {'motion_command_topic': execution_motion_command_topic},
            {'output_command_topic': '/servo/command'},
            {'state_topic': execution_state_topic},
            {'estop_topic': execution_estop_topic},
            {'teleop_timeout_sec': LaunchConfiguration('execution_teleop_timeout_sec')},
            {'motion_timeout_sec': LaunchConfiguration('execution_motion_timeout_sec')},
            {'debug': LaunchConfiguration('execution_debug')},
        ],
    )

    bridge_node = Node(
        package='websocket_bridge',
        executable='bridge_node',
        name='websocket_ros2_bridge',
        output='screen',
        parameters=[
            {'ws_host': LaunchConfiguration('ws_host')},
            {'ws_port': LaunchConfiguration('ws_port')},
            {'device_id': LaunchConfiguration('device_id')},
            {'debug': LaunchConfiguration('bridge_debug')},
            {'command_topic': execution_teleop_command_topic},
            {'teleop_control_topic': execution_teleop_control_topic},
            {'execution_state_topic': execution_state_topic},
            {
                'extension_factories': LaunchConfiguration(
                    'bridge_extension_factories'
                ),
            },
            {'imu_debug': LaunchConfiguration('imu_debug')},
            {'heartbeat_debug': LaunchConfiguration('heartbeat_debug')},
            {'ws_debug': LaunchConfiguration('ws_debug')},
            {'debug_aggregate': LaunchConfiguration('debug_aggregate')},
            {'debug_aggregate_period': LaunchConfiguration('debug_aggregate_period')},
            {'debug_aggregate_max_len': LaunchConfiguration('debug_aggregate_max_len')},
        ],
    )

    log_info = LogInfo(
        msg=[
            '[robot_bringup/teleop] WebSocket 与执行仲裁链路已装配\n',
            '  WebSocket: ws://',
            LaunchConfiguration('ws_host'),
            ':',
            LaunchConfiguration('ws_port'),
            '\n',
            '  Teleop入口: ',
            execution_teleop_command_topic,
            '\n',
            '  Teleop控制权: ',
            execution_teleop_control_topic,
            '\n',
            '  Motion入口: ',
            execution_motion_command_topic,
            '\n',
            '  执行状态: ',
            execution_state_topic,
            '\n',
        ],
    )

    return LaunchDescription([
        debug_arg,
        ws_host_arg,
        ws_port_arg,
        device_id_arg,
        enable_execution_manager_arg,
        execution_teleop_command_topic_arg,
        execution_teleop_control_topic_arg,
        execution_motion_command_topic_arg,
        execution_state_topic_arg,
        execution_estop_topic_arg,
        execution_teleop_timeout_sec_arg,
        execution_motion_timeout_sec_arg,
        execution_debug_arg,
        bridge_debug_arg,
        bridge_extension_factories_arg,
        imu_debug_arg,
        heartbeat_debug_arg,
        ws_debug_arg,
        debug_aggregate_arg,
        debug_aggregate_period_arg,
        debug_aggregate_max_len_arg,
        log_info,
        execution_manager_node,
        bridge_node,
    ])
