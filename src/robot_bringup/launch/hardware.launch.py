"""hardware bringup launch."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from robot_bringup.launch_utils import get_protocol_cache_default
from robot_bringup.launch_utils import load_servo_map


def generate_launch_description():
    """Generate hardware stack launch description."""
    config_file, servo_map = load_servo_map()
    protocol_cache_default = get_protocol_cache_default(config_file)

    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='是否启用调试模式',
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

    bus_port_nodes = []
    servo_info_lines = []
    for index, (port, servo_ids) in enumerate(servo_map.items()):
        if not servo_ids:
            servo_info_lines.append(f'    - {port} (舵机ID: 无 - 已跳过)\n')
            print(f'  ⊘ 跳过端口 {port}（未配置舵机ID）')
            continue

        bus_port_nodes.append(
            Node(
                package='servo_hardware',
                executable='bus_port_driver',
                name=f'bus_port_driver_{index}',
                output='screen',
                parameters=[
                    {'port': port},
                    {'baudrate': LaunchConfiguration('baudrate')},
                    {'default_speed': 100},
                    {'zl_servo_ids': servo_ids},
                    {'lx_servo_ids': servo_ids},
                    {'debug': LaunchConfiguration('bus_servo_debug')},
                    {'log_id': True},
                ],
            )
        )
        servo_ids_str = ', '.join(map(str, servo_ids))
        servo_info_lines.append(f'    - {port} (舵机ID: {servo_ids_str})\n')

    bus_protocol_router_node = Node(
        package='servo_hardware',
        executable='bus_protocol_router',
        name='bus_protocol_router',
        output='screen',
        parameters=[
            {'bus_map_file': config_file},
            {'protocol_cache_file': LaunchConfiguration('protocol_cache_file')},
            {'manual_protocol_map_file': LaunchConfiguration('manual_protocol_map_file')},
            {'lx_id_ranges': LaunchConfiguration('lx_id_ranges')},
            {'zl_id_ranges': LaunchConfiguration('zl_id_ranges')},
            {'probe_on_startup': LaunchConfiguration('probe_on_startup')},
            {'probe_timeout_sec': LaunchConfiguration('probe_timeout_sec')},
            {'probe_on_unknown_command': LaunchConfiguration('probe_on_unknown_command')},
            {'probe_retry_interval_sec': LaunchConfiguration('probe_retry_interval_sec')},
            {'runtime_probe_interval_sec': LaunchConfiguration('runtime_probe_interval_sec')},
            {'read_service_timeout_sec': LaunchConfiguration('read_service_timeout_sec')},
            {'probe_wait_service_sec': 6.0},
            {'debug': LaunchConfiguration('bus_servo_debug')},
        ],
    )

    imu_driver_node = Node(
        package='sensor_hardware',
        executable='imu_serial_driver',
        name='imu_serial_driver',
        output='screen',
        condition=IfCondition(LaunchConfiguration('imu_enable')),
        parameters=[
            {'port': LaunchConfiguration('imu_port')},
            {'baudrate': LaunchConfiguration('imu_baudrate')},
            {'publish_rate': LaunchConfiguration('imu_publish_rate')},
            {'debug': LaunchConfiguration('imu_debug')},
            {'algo_type': LaunchConfiguration('imu_algo_type')},
            {'calibrate_on_start': False},
            {'sensor_id': LaunchConfiguration('imu_sensor_id')},
        ],
        remappings=[
            ('~/data', '/sensor/imu'),
        ],
    )

    log_info = LogInfo(
        msg=[
            '[robot_bringup/hardware] 驱动链路已装配\n',
            '  总线映射文件: ',
            config_file,
            '\n',
            '  协议缓存文件: ',
            LaunchConfiguration('protocol_cache_file'),
            '\n',
            '  总线驱动板:\n',
            *servo_info_lines,
            '  IMU节点启用: ',
            LaunchConfiguration('imu_enable'),
            '\n',
            '  IMU串口: ',
            LaunchConfiguration('imu_port'),
            ' @ ',
            LaunchConfiguration('imu_baudrate'),
            ' bps\n',
            '  PCA9685: 已禁用 (I2C设备未连接)\n',
        ],
    )

    return LaunchDescription([
        debug_arg,
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
        *bus_port_nodes,
        bus_protocol_router_node,
        imu_driver_node,
    ])
