import os
from glob import glob
from setuptools import setup

package_name = 'n3mo_control'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kifen',
    maintainer_email='kifenraph@gmail.com',
    description='N3mo marine sim control nodes.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'target_pose_publisher = n3mo_control.target_pose_publisher:main',
            'env_control = n3mo_control.env_control:main',
            'map_publisher = n3mo_control.map_publisher:main',
        ],
    },
)
