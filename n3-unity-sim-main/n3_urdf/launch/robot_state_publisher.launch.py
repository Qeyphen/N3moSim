"""Launch robot_state_publisher with the n3_urdf xacro model."""

import os
import subprocess

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    xacro_file = os.path.join(
        get_package_share_directory("n3_urdf"), "urdf", "n3_urdf.urdf.xacro"
    )

    # Resolve xacro at launch time
    urdf_string = subprocess.check_output(["xacro", xacro_file]).decode("utf-8")

    return LaunchDescription(
        [
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                output="screen",
                parameters=[{"robot_description": urdf_string}],
            ),
        ]
    )
