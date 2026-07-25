"""
3-DOF并联控制器Launch文件

启动3-DOF并联控制器节点
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """生成Launch描述"""

    # 获取包的共享目录
    pkg_share = FindPackageShare('parallel_3dof_controller')

    # 配置文件路径
    default_config_file = PathJoinSubstitution([
        pkg_share,
        'config',
        'parallel_3dof_params.yaml'
    ])

    # 声明Launch参数
    ankle_side_arg = DeclareLaunchArgument(
        'ankle_side',
        default_value='right',
        description='控制哪侧脚踝 (right/left)'
    )

    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用调试模式'
    )

    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config_file,
        description='配置文件路径'
    )

    command_topic_arg = DeclareLaunchArgument(
        'command_topic',
        default_value='/execution/motion/command',
        description='舵机命令输出话题，默认接入 execution_manager'
    )
    task_command_topic_arg = DeclareLaunchArgument(
        'task_command_topic',
        default_value='/execution/task/command',
        description='携带正式 task lease 的执行命令入口',
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
    motion_action_name_arg = DeclareLaunchArgument(
        'motion_action_name',
        default_value='/motion/execute',
        description='内部结构化运动执行 Action',
    )
    enable_motion_action_server_arg = DeclareLaunchArgument(
        'enable_motion_action_server',
        default_value='true',
        description='是否持有正式 motion ActionServer',
    )
    require_scene_context_arg = DeclareLaunchArgument(
        'require_scene_context',
        default_value='false',
        description='是否在 task lease 和执行命令前强制校验结构化场景',
    )
    scene_state_topic_arg = DeclareLaunchArgument(
        'scene_state_topic',
        default_value='/perception/scene_state',
        description='motion owner 消费的完整结构化场景话题',
    )
    scene_max_age_sec_arg = DeclareLaunchArgument(
        'scene_max_age_sec',
        default_value='2.0',
        description='允许 motion 准入使用的场景最大接收年龄',
    )
    scene_required_frame_id_arg = DeclareLaunchArgument(
        'scene_required_frame_id',
        default_value='camera_link',
        description='目标对象几何所在的唯一受信任坐标系',
    )
    scene_target_min_confidence_arg = DeclareLaunchArgument(
        'scene_target_min_confidence',
        default_value='0.6',
        description='目标脚踝对象进入 motion owner 的最低置信度',
    )
    scene_target_max_extent_m_arg = DeclareLaunchArgument(
        'scene_target_max_extent_m',
        default_value='2.0',
        description='目标对象 AABB 各轴允许的最大绝对边界',
    )
    read_actuator_position_service_arg = DeclareLaunchArgument(
        'read_actuator_position_service',
        default_value='/execution/read_actuator_position',
        description='task lease 保护的实际位置读取服务',
    )
    stop_actuators_service_arg = DeclareLaunchArgument(
        'stop_actuators_service',
        default_value='/execution/stop_actuators',
        description='task lease 保护的执行器停止请求服务',
    )
    task_lease_wait_timeout_sec_arg = DeclareLaunchArgument(
        'task_lease_wait_timeout_sec',
        default_value='2.0',
        description='等待 execution_manager task lease 的最长秒数',
    )
    task_terminal_wait_timeout_sec_arg = DeclareLaunchArgument(
        'task_terminal_wait_timeout_sec',
        default_value='2.0',
        description='等待 execution_manager task 终态的最长秒数',
    )
    task_keepalive_period_sec_arg = DeclareLaunchArgument(
        'task_keepalive_period_sec',
        default_value='1.0',
        description='task lease 续租周期',
    )
    feedback_poll_period_sec_arg = DeclareLaunchArgument(
        'feedback_poll_period_sec',
        default_value='0.05',
        description='实际位置采样周期',
    )
    service_call_timeout_sec_arg = DeclareLaunchArgument(
        'service_call_timeout_sec',
        default_value='1.0',
        description='motion-level 服务调用超时',
    )
    stable_sample_count_arg = DeclareLaunchArgument(
        'stable_sample_count',
        default_value='3',
        description='完成或停止确认所需连续稳定样本数',
    )
    stop_position_tolerance_arg = DeclareLaunchArgument(
        'stop_position_tolerance',
        default_value='1',
        description='连续位置采样确认停止时允许的原始位置变化',
    )

    # 3-DOF并联控制器节点
    parallel_3dof_controller_node = Node(
        package='parallel_3dof_controller',
        executable='parallel_3dof_node',  # 修正：与 setup.py 中的 entry_point 一致
        name='parallel_3dof_controller',
        namespace='',
        parameters=[
            LaunchConfiguration('config_file'),
            {
                'ankle_side': LaunchConfiguration('ankle_side'),
                'debug': LaunchConfiguration('debug'),
                'command_topic': LaunchConfiguration('command_topic'),
                'task_command_topic': LaunchConfiguration('task_command_topic'),
                'task_control_topic': LaunchConfiguration('task_control_topic'),
                'task_state_topic': LaunchConfiguration('task_state_topic'),
                'motion_action_name': LaunchConfiguration('motion_action_name'),
                'enable_motion_action_server': LaunchConfiguration(
                    'enable_motion_action_server'
                ),
                'require_scene_context': LaunchConfiguration(
                    'require_scene_context'
                ),
                'scene_state_topic': LaunchConfiguration('scene_state_topic'),
                'scene_max_age_sec': LaunchConfiguration('scene_max_age_sec'),
                'scene_required_frame_id': LaunchConfiguration(
                    'scene_required_frame_id'
                ),
                'scene_target_min_confidence': LaunchConfiguration(
                    'scene_target_min_confidence'
                ),
                'scene_target_max_extent_m': LaunchConfiguration(
                    'scene_target_max_extent_m'
                ),
                'read_actuator_position_service': LaunchConfiguration(
                    'read_actuator_position_service'
                ),
                'stop_actuators_service': LaunchConfiguration(
                    'stop_actuators_service'
                ),
                'task_lease_wait_timeout_sec': LaunchConfiguration(
                    'task_lease_wait_timeout_sec'
                ),
                'task_terminal_wait_timeout_sec': LaunchConfiguration(
                    'task_terminal_wait_timeout_sec'
                ),
                'task_keepalive_period_sec': LaunchConfiguration(
                    'task_keepalive_period_sec'
                ),
                'feedback_poll_period_sec': LaunchConfiguration(
                    'feedback_poll_period_sec'
                ),
                'service_call_timeout_sec': LaunchConfiguration(
                    'service_call_timeout_sec'
                ),
                'stable_sample_count': LaunchConfiguration('stable_sample_count'),
                'stop_position_tolerance': LaunchConfiguration(
                    'stop_position_tolerance'
                ),
            }
        ],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        ankle_side_arg,
        debug_arg,
        config_file_arg,
        command_topic_arg,
        task_command_topic_arg,
        task_control_topic_arg,
        task_state_topic_arg,
        motion_action_name_arg,
        enable_motion_action_server_arg,
        require_scene_context_arg,
        scene_state_topic_arg,
        scene_max_age_sec_arg,
        scene_required_frame_id_arg,
        scene_target_min_confidence_arg,
        scene_target_max_extent_m_arg,
        read_actuator_position_service_arg,
        stop_actuators_service_arg,
        task_lease_wait_timeout_sec_arg,
        task_terminal_wait_timeout_sec_arg,
        task_keepalive_period_sec_arg,
        feedback_poll_period_sec_arg,
        service_call_timeout_sec_arg,
        stable_sample_count_arg,
        stop_position_tolerance_arg,
        parallel_3dof_controller_node,
    ])
