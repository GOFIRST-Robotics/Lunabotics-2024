from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch import LaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    bringup_dir = get_package_share_directory("isaac_ros_launch")

    setup_for_zed_arg = DeclareLaunchArgument(
        "setup_for_zed",
        default_value="False",
        description="Whether to run from live zed data",
    )
    setup_for_gazebo_arg = DeclareLaunchArgument(
        "setup_for_gazebo",
        default_value="True",
        description="Whether to run in gazebo",
    )
    ld = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, "isaac_launch.py")),
        launch_arguments={
            "setup_for_zed": "False",
            "setup_for_gazebo": "True",
        }.items(),
    )

    return LaunchDescription([setup_for_zed_arg, setup_for_gazebo_arg, ld])
