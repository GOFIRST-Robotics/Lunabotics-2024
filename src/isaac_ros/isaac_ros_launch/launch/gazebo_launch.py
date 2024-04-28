from launch.actions import IncludeLaunchDescription
from launch import LaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    bringup_dir = get_package_share_directory("isaac_ros_launch")

    ld = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, "isaac_launch.py")),
        launch_arguments={
            "setup_for_zed": "False",
            "setup_for_gazebo": "True",
            "use_nvblox": "False",
        }.items(),
    )

    return LaunchDescription([ld])
