"""完整系统 bringup launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from robot_bringup.launch_utils import get_protocol_cache_default
from robot_bringup.launch_utils import resolve_bus_config_file


def generate_launch_description():
    """Generate full system launch description."""
    protocol_cache_default = get_protocol_cache_default(resolve_bus_config_file())

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
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用调试模式',
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
    bus_servo_debug_arg = DeclareLaunchArgument(
        'bus_servo_debug',
        default_value='true',
        description='总线舵机驱动调试模式',
    )
    protocol_cache_file_arg = DeclareLaunchArgument(
        'protocol_cache_file',
        default_value=protocol_cache_default,
        description='总线协议探测缓存文件路径',
    )
    manual_protocol_map_file_arg = DeclareLaunchArgument(
        'manual_protocol_map_file',
        default_value='',
        description='手动协议映射文件(可选，优先级高于缓存/范围)',
    )
    lx_id_ranges_arg = DeclareLaunchArgument(
        'lx_id_ranges',
        default_value='21-34',
        description='幻尔协议ID范围(逗号分隔，如21-34,60-64)',
    )
    zl_id_ranges_arg = DeclareLaunchArgument(
        'zl_id_ranges',
        default_value='35-43',
        description='众灵协议ID范围(逗号分隔，如35-43)',
    )
    probe_on_startup_arg = DeclareLaunchArgument(
        'probe_on_startup',
        default_value='true',
        description='是否在启动时探测未知ID协议',
    )
    probe_timeout_sec_arg = DeclareLaunchArgument(
        'probe_timeout_sec',
        default_value='0.2',
        description='单次协议探测超时(秒)',
    )
    probe_on_unknown_command_arg = DeclareLaunchArgument(
        'probe_on_unknown_command',
        default_value='true',
        description='未知ID收到命令时是否触发在线探测',
    )
    probe_retry_interval_sec_arg = DeclareLaunchArgument(
        'probe_retry_interval_sec',
        default_value='3.0',
        description='未知ID在线探测失败后重试最小间隔(秒)',
    )
    runtime_probe_interval_sec_arg = DeclareLaunchArgument(
        'runtime_probe_interval_sec',
        default_value='0.05',
        description='后台在线探测任务轮询周期(秒)',
    )
    read_service_timeout_sec_arg = DeclareLaunchArgument(
        'read_service_timeout_sec',
        default_value='0.35',
        description='全局读角度服务超时(秒)',
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
    enable_simulation_arg = DeclareLaunchArgument(
        'enable_simulation',
        default_value='true',
        description='是否启动simulation域桥接链路',
    )
    baudrate_arg = DeclareLaunchArgument(
        'baudrate',
        default_value='115200',
        description='总线舵机波特率',
    )
    i2c_address_arg = DeclareLaunchArgument(
        'i2c_address',
        default_value='64',
        description='PCA9685 I2C地址 (十进制)',
    )
    i2c_bus_arg = DeclareLaunchArgument(
        'i2c_bus',
        default_value='1',
        description='I2C总线号',
    )
    imu_port_arg = DeclareLaunchArgument(
        'imu_port',
        default_value='/dev/ttyAMA4',
        description='IMU 串口设备路径',
    )
    imu_baudrate_arg = DeclareLaunchArgument(
        'imu_baudrate',
        default_value='115200',
        description='IMU 串口波特率',
    )
    imu_debug_arg = DeclareLaunchArgument(
        'imu_debug',
        default_value='false',
        description='IMU 是否启用调试模式',
    )
    imu_publish_rate_arg = DeclareLaunchArgument(
        'imu_publish_rate',
        default_value='50.0',
        description='IMU 数据发布频率(Hz)',
    )
    imu_algo_type_arg = DeclareLaunchArgument(
        'imu_algo_type',
        default_value='9',
        description='IMU 融合算法类型(6=六轴, 9=九轴)',
    )
    imu_sensor_id_arg = DeclareLaunchArgument(
        'imu_sensor_id',
        default_value='0',
        description='IMU 传感器ID',
    )
    imu_enable_arg = DeclareLaunchArgument(
        'imu_enable',
        default_value='false',
        description='是否启动IMU节点',
    )
    pca_debug_arg = DeclareLaunchArgument(
        'pca_debug',
        default_value=LaunchConfiguration('debug'),
        description='PCA9685 舵机驱动调试模式',
    )

    teleop_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('robot_bringup'),
                'launch',
                'teleop.launch.py',
            ])
        ),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
            'ws_host': LaunchConfiguration('ws_host'),
            'ws_port': LaunchConfiguration('ws_port'),
            'device_id': LaunchConfiguration('device_id'),
            'enable_execution_manager': LaunchConfiguration('enable_execution_manager'),
            'execution_teleop_command_topic': LaunchConfiguration('execution_teleop_command_topic'),
            'execution_teleop_control_topic': LaunchConfiguration('execution_teleop_control_topic'),
            'execution_motion_command_topic': LaunchConfiguration('execution_motion_command_topic'),
            'execution_state_topic': LaunchConfiguration('execution_state_topic'),
            'execution_estop_topic': LaunchConfiguration('execution_estop_topic'),
            'execution_teleop_timeout_sec': LaunchConfiguration('execution_teleop_timeout_sec'),
            'execution_motion_timeout_sec': LaunchConfiguration('execution_motion_timeout_sec'),
            'execution_debug': LaunchConfiguration('execution_debug'),
            'bridge_debug': LaunchConfiguration('bridge_debug'),
            'imu_debug': LaunchConfiguration('imu_debug'),
            'heartbeat_debug': LaunchConfiguration('heartbeat_debug'),
            'ws_debug': LaunchConfiguration('ws_debug'),
            'debug_aggregate': LaunchConfiguration('debug_aggregate'),
            'debug_aggregate_period': LaunchConfiguration('debug_aggregate_period'),
            'debug_aggregate_max_len': LaunchConfiguration('debug_aggregate_max_len'),
        }.items(),
    )

    hardware_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('robot_bringup'),
                'launch',
                'hardware.launch.py',
            ])
        ),
        launch_arguments={
            'debug': LaunchConfiguration('debug'),
            'bus_servo_debug': LaunchConfiguration('bus_servo_debug'),
            'protocol_cache_file': LaunchConfiguration('protocol_cache_file'),
            'manual_protocol_map_file': LaunchConfiguration('manual_protocol_map_file'),
            'lx_id_ranges': LaunchConfiguration('lx_id_ranges'),
            'zl_id_ranges': LaunchConfiguration('zl_id_ranges'),
            'probe_on_startup': LaunchConfiguration('probe_on_startup'),
            'probe_timeout_sec': LaunchConfiguration('probe_timeout_sec'),
            'probe_on_unknown_command': LaunchConfiguration('probe_on_unknown_command'),
            'probe_retry_interval_sec': LaunchConfiguration('probe_retry_interval_sec'),
            'runtime_probe_interval_sec': LaunchConfiguration('runtime_probe_interval_sec'),
            'read_service_timeout_sec': LaunchConfiguration('read_service_timeout_sec'),
            'baudrate': LaunchConfiguration('baudrate'),
            'i2c_address': LaunchConfiguration('i2c_address'),
            'i2c_bus': LaunchConfiguration('i2c_bus'),
            'imu_port': LaunchConfiguration('imu_port'),
            'imu_baudrate': LaunchConfiguration('imu_baudrate'),
            'imu_debug': LaunchConfiguration('imu_debug'),
            'imu_publish_rate': LaunchConfiguration('imu_publish_rate'),
            'imu_algo_type': LaunchConfiguration('imu_algo_type'),
            'imu_sensor_id': LaunchConfiguration('imu_sensor_id'),
            'imu_enable': LaunchConfiguration('imu_enable'),
            'pca_debug': LaunchConfiguration('pca_debug'),
        }.items(),
    )

    simulation_stack = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('robot_bringup'),
                'launch',
                'simulation.launch.py',
            ])
        ),
        launch_arguments={
            'enable_simulation': LaunchConfiguration('enable_simulation'),
        }.items(),
    )

    log_info = LogInfo(
        msg=[
            '========================================\n',
            '  robot_bringup 完整系统已启动\n',
            '========================================\n',
            '  子链路:\n',
            '    - teleop.launch.py\n',
            '    - hardware.launch.py\n',
            '    - simulation.launch.py\n',
            '  WebSocket: ws://',
            LaunchConfiguration('ws_host'),
            ':',
            LaunchConfiguration('ws_port'),
            '\n',
            '  Teleop入口: ',
            LaunchConfiguration('execution_teleop_command_topic'),
            '\n',
            '  Teleop控制权: ',
            LaunchConfiguration('execution_teleop_control_topic'),
            '\n',
            '  Motion入口: ',
            LaunchConfiguration('execution_motion_command_topic'),
            '\n',
            '  执行状态: ',
            LaunchConfiguration('execution_state_topic'),
            '\n',
            '  仿真域启用: ',
            LaunchConfiguration('enable_simulation'),
            '\n',
            '========================================\n',
        ],
    )

    return LaunchDescription([
        ws_host_arg,
        ws_port_arg,
        device_id_arg,
        debug_arg,
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
        bus_servo_debug_arg,
        protocol_cache_file_arg,
        manual_protocol_map_file_arg,
        lx_id_ranges_arg,
        zl_id_ranges_arg,
        probe_on_startup_arg,
        probe_timeout_sec_arg,
        probe_on_unknown_command_arg,
        probe_retry_interval_sec_arg,
        runtime_probe_interval_sec_arg,
        read_service_timeout_sec_arg,
        heartbeat_debug_arg,
        ws_debug_arg,
        debug_aggregate_arg,
        debug_aggregate_period_arg,
        debug_aggregate_max_len_arg,
        enable_simulation_arg,
        baudrate_arg,
        i2c_address_arg,
        i2c_bus_arg,
        imu_port_arg,
        imu_baudrate_arg,
        imu_debug_arg,
        imu_publish_rate_arg,
        imu_algo_type_arg,
        imu_sensor_id_arg,
        imu_enable_arg,
        pca_debug_arg,
        log_info,
        teleop_stack,
        hardware_stack,
        simulation_stack,
    ])
