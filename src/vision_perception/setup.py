from glob import glob
import os

from setuptools import find_packages, setup


package_name = 'vision_perception'


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
        (
            os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py'),
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='chenpeel',
    maintainer_email='chenpeel@foxmail.com',
    description='将视觉边缘输入转换为结构化场景状态',
    license='MIT',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'vision_perception_node = '
            'vision_perception.vision_perception_node:main',
        ],
    },
)
