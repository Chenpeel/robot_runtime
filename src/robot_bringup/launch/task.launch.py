"""正式任务与运动执行链路 bringup launch。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """装配唯一 task Action、motion Action 与执行仲裁链路。"""
    enable_execution_manager_arg = DeclareLaunchArgument(
        'enable_execution_manager',
        default_value='true',
        description='是否启动 task/teleop 共用的执行仲裁节点',
    )
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用任务执行链路调试模式',
    )
    ankle_side_arg = DeclareLaunchArgument(
        'ankle_side',
        default_value='right',
        description='当前运动执行 owner 控制的脚踝侧 (right/left)',
    )
    task_action_name_arg = DeclareLaunchArgument(
        'task_action_name',
        default_value='/task/execute',
        description='对外唯一正式任务 Action 名称',
    )
    motion_action_name_arg = DeclareLaunchArgument(
        'motion_action_name',
        default_value='/motion/execute',
        description='内部唯一运动执行 Action 名称',
    )
    motion_server_wait_timeout_sec_arg = DeclareLaunchArgument(
        'motion_server_wait_timeout_sec',
        default_value='5.0',
        description='task bridge 等待 motion Action Server 的最长秒数',
    )
    enable_context_arg = DeclareLaunchArgument(
        'enable_context',
        default_value='true',
        description='是否启用 task bridge 的结构化上下文边界',
    )
    speech_intent_topic_arg = DeclareLaunchArgument(
        'speech_intent_topic',
        default_value='/speech/intent',
        description='task bridge 消费的结构化语音意图话题',
    )
    perception_scene_topic_arg = DeclareLaunchArgument(
        'perception_scene_topic',
        default_value='/perception/scene_state',
        description='task bridge 消费的结构化感知场景话题',
    )
    task_context_topic_arg = DeclareLaunchArgument(
        'task_context_topic',
        default_value='/task/context_signal',
        description='task bridge 对外发布的结构化上下文话题',
    )
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
        description='携带正式 task lease 的执行命令话题',
    )
    task_control_topic_arg = DeclareLaunchArgument(
        'task_control_topic',
        default_value='/execution/task/control',
        description='正式 task 执行租约控制话题',
    )
    task_state_topic_arg = DeclareLaunchArgument(
        'task_state_topic',
        default_value='/execution/task/state',
        description='正式 task 执行租约状态话题',
    )
    motion_command_topic_arg = DeclareLaunchArgument(
        'motion_command_topic',
        default_value='/execution/motion/command',
        description='非 task motion 执行请求话题',
    )
    state_topic_arg = DeclareLaunchArgument(
        'state_topic',
        default_value='/execution/state',
        description='执行层状态话题',
    )
    actuator_state_topic_arg = DeclareLaunchArgument(
        'actuator_state_topic',
        default_value='/execution/actuator_state',
        description='执行层向上发布的执行器状态话题',
    )
    read_actuator_position_service_arg = DeclareLaunchArgument(
        'read_actuator_position_service',
        default_value='/execution/read_actuator_position',
        description='受 task lease 保护的实际位置读取服务',
    )
    stop_actuators_service_arg = DeclareLaunchArgument(
        'stop_actuators_service',
        default_value='/execution/stop_actuators',
        description='受 task lease 保护的执行器停止请求服务',
    )
    driver_read_position_service_arg = DeclareLaunchArgument(
        'driver_read_position_service',
        default_value='/servo/read_position',
        description='execution_manager 使用的驱动级位置读取服务',
    )
    driver_execute_command_service_arg = DeclareLaunchArgument(
        'driver_execute_command_service',
        default_value='/servo/execute_command',
        description='execution_manager 使用的驱动级命令服务',
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
        description='正式 task lease 超时(秒)',
    )
    driver_service_timeout_sec_arg = DeclareLaunchArgument(
        'driver_service_timeout_sec',
        default_value='2.0',
        description='execution_manager 等待驱动级服务响应的最长秒数',
    )

    execution_manager_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('execution_manager'),
                'launch',
                'execution_manager.launch.py',
            ])
        ),
        condition=IfCondition(LaunchConfiguration('enable_execution_manager')),
        launch_arguments={
            'teleop_command_topic': LaunchConfiguration('teleop_command_topic'),
            'teleop_control_topic': LaunchConfiguration('teleop_control_topic'),
            'task_command_topic': LaunchConfiguration('task_command_topic'),
            'task_control_topic': LaunchConfiguration('task_control_topic'),
            'motion_command_topic': LaunchConfiguration('motion_command_topic'),
            'actuator_state_topic': LaunchConfiguration('actuator_state_topic'),
            'state_topic': LaunchConfiguration('state_topic'),
            'task_state_topic': LaunchConfiguration('task_state_topic'),
            'read_actuator_position_service': LaunchConfiguration(
                'read_actuator_position_service'
            ),
            'stop_actuators_service': LaunchConfiguration(
                'stop_actuators_service'
            ),
            'driver_read_position_service': LaunchConfiguration(
                'driver_read_position_service'
            ),
            'driver_execute_command_service': LaunchConfiguration(
                'driver_execute_command_service'
            ),
            'driver_safety_topic': LaunchConfiguration('driver_safety_topic'),
            'driver_safety_service': LaunchConfiguration('driver_safety_service'),
            'estop_topic': LaunchConfiguration('estop_topic'),
            'teleop_timeout_sec': LaunchConfiguration('teleop_timeout_sec'),
            'motion_timeout_sec': LaunchConfiguration('motion_timeout_sec'),
            'task_timeout_sec': LaunchConfiguration('task_timeout_sec'),
            'driver_service_timeout_sec': LaunchConfiguration(
                'driver_service_timeout_sec'
            ),
            'debug': LaunchConfiguration('debug'),
        }.items(),
    )

    motion_owner_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('parallel_3dof_controller'),
                'launch',
                'parallel_3dof_controller.launch.py',
            ])
        ),
        launch_arguments={
            'ankle_side': LaunchConfiguration('ankle_side'),
            'debug': LaunchConfiguration('debug'),
            'command_topic': LaunchConfiguration('motion_command_topic'),
            'task_command_topic': LaunchConfiguration('task_command_topic'),
            'task_control_topic': LaunchConfiguration('task_control_topic'),
            'task_state_topic': LaunchConfiguration('task_state_topic'),
            'motion_action_name': LaunchConfiguration('motion_action_name'),
            'read_actuator_position_service': LaunchConfiguration(
                'read_actuator_position_service'
            ),
            'stop_actuators_service': LaunchConfiguration(
                'stop_actuators_service'
            ),
        }.items(),
    )

    task_bridge_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('task_service_bridge'),
                'launch',
                'task_service_bridge.launch.py',
            ])
        ),
        launch_arguments={
            'task_action_name': LaunchConfiguration('task_action_name'),
            'motion_action_name': LaunchConfiguration('motion_action_name'),
            'motion_server_wait_timeout_sec': LaunchConfiguration(
                'motion_server_wait_timeout_sec'
            ),
            'enable_context': LaunchConfiguration('enable_context'),
            'speech_intent_topic': LaunchConfiguration('speech_intent_topic'),
            'perception_scene_topic': LaunchConfiguration(
                'perception_scene_topic'
            ),
            'task_context_topic': LaunchConfiguration('task_context_topic'),
        }.items(),
    )

    log_info = LogInfo(
        msg=[
            '[robot_bringup/task] 正式任务执行链路已装配\n',
            '  Task Action: ',
            LaunchConfiguration('task_action_name'),
            '\n',
            '  Motion Action: ',
            LaunchConfiguration('motion_action_name'),
            '\n',
            '  Task命令入口: ',
            LaunchConfiguration('task_command_topic'),
            '\n',
            '  Task租约控制: ',
            LaunchConfiguration('task_control_topic'),
            '\n',
            '  Task租约状态: ',
            LaunchConfiguration('task_state_topic'),
            '\n',
            '  实际位置读取: ',
            LaunchConfiguration('read_actuator_position_service'),
            '\n',
            '  执行器停止: ',
            LaunchConfiguration('stop_actuators_service'),
            '\n',
        ],
    )

    return LaunchDescription([
        enable_execution_manager_arg,
        debug_arg,
        ankle_side_arg,
        task_action_name_arg,
        motion_action_name_arg,
        motion_server_wait_timeout_sec_arg,
        enable_context_arg,
        speech_intent_topic_arg,
        perception_scene_topic_arg,
        task_context_topic_arg,
        teleop_command_topic_arg,
        teleop_control_topic_arg,
        task_command_topic_arg,
        task_control_topic_arg,
        task_state_topic_arg,
        motion_command_topic_arg,
        state_topic_arg,
        actuator_state_topic_arg,
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
        log_info,
        execution_manager_stack,
        motion_owner_stack,
        task_bridge_stack,
    ])
