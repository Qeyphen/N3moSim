from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        DeclareLaunchArgument('topic', default_value='/agent_01/target_pose'),
        DeclareLaunchArgument('frame_id', default_value='map'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.0'),
        DeclareLaunchArgument('wait_timeout', default_value='5.0'),
        DeclareLaunchArgument('settle_time', default_value='0.5'),
    ]

    node = Node(
        package='n3mo_control',
        executable='target_pose_publisher',
        name='target_pose_publisher',
        output='screen',
        parameters=[{
            'topic': LaunchConfiguration('topic'),
            'frame_id': LaunchConfiguration('frame_id'),
            'x': LaunchConfiguration('x'),
            'z': LaunchConfiguration('z'),
            'wait_timeout': LaunchConfiguration('wait_timeout'),
            'settle_time': LaunchConfiguration('settle_time'),
        }],
    )

    return LaunchDescription(args + [node])
