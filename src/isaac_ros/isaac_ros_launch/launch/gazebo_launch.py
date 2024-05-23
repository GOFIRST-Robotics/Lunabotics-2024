from launch_ros.substitutions import FindPackageShare

from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch import LaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution


def generate_launch_description():

    use_nvblox_arg = DeclareLaunchArgument(
        "use_nvblox",
        default_value="False",
        description="Whether to run nvblox",
    )

    ld = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("isaac_ros_launch"), "isaac_launch.py"])
        ),
        launch_arguments={
            "setup_for_zed": "False",
            "setup_for_gazebo": "True",
            "use_nvblox": LaunchConfiguration("use_nvblox"),
        }.items(),
    )

    return LaunchDescription([use_nvblox_arg, ld])
