from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'execution_manager'

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
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'rclpy'],
    zip_safe=True,
    maintainer='chenpeel',
    maintainer_email='chenpeel@foxmail.com',
    description='执行协调与安全仲裁节点',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'execution_manager_node = execution_manager.execution_manager_node:main',
        ],
    },
)
