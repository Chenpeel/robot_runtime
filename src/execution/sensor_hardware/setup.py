from setuptools import find_packages, setup

package_name = 'sensor_hardware'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(include=[package_name, package_name + '.*']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'rclpy',
        'pyserial',
        'smbus2',
    ],
    zip_safe=True,
    maintainer='chenpeel',
    maintainer_email='chenpeel@foxmail.com',
    description='传感器硬件接口，用于 IMU 等底层传感器控制',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'imu_driver = sensor_hardware.imu_driver:main',
            'imu_serial_driver = sensor_hardware.imu_serial_driver:main',
        ],
    },
)
