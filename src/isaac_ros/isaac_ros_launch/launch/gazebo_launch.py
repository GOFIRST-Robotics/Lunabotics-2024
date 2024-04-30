from launch.actions import IncludeLaunchDescription,DeclareLaunchArgument
from launch import LaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration
import os


def generate_launch_description():
    bringup_dir = get_package_share_directory("isaac_ros_launch")

    use_nvblox_arg = DeclareLaunchArgument(
        "use_nvblox",
        default_value="False",
        description="Whether to run nvblox",
    )

    ld = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, "isaac_launch.py")),
        launch_arguments={
            "setup_for_zed": "False",
            "setup_for_gazebo": "True",
            "use_nvblox": LaunchConfiguration("use_nvblox"),
        }.items(),
    )

    return LaunchDescription([use_nvblox_arg,ld])
