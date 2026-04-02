
from setuptools import setup

import os

from glob import glob

package_name = 'n3mo_control'

setup(

    name=package_name,

    version='0.1.0',

    packages=[package_name],

    data_files=[

        ('share/ament_index/resource_index/packages',

            ['resource/' + package_name]),

        ('share/' + package_name, ['package.xml']),

        # Install config files

        (os.path.join('share', package_name, 'config'),

            glob('config/*.json')),

    ],

    install_requires=['setuptools'],

    zip_safe=True,

    maintainer='N3moSim',

    maintainer_email='kifenraph@gmail.com',

    description='N3moSim ROS2 control package for autonomous sailboat simulation',

    license='MIT',

    entry_points={

        'console_scripts': [

            'n3mo_controller    = n3mo_control.n3mo_controller:main',

            'mission_planner    = n3mo_control.mission_planner:main',

            'sensor_publisher   = n3mo_control.sensor_publisher:main',

            'obstacle_detector  = n3mo_control.obstacle_detector:main',

        ],

    },

)

