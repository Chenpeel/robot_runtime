from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'robot_bringup'

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
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='chenpeel',
    maintainer_email='chenpeel@foxmail.com',
    description='系统级 bringup 包，负责组合 teleop、hardware、simulation 等运行链路',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
)
