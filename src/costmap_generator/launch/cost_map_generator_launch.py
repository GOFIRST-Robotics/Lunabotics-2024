from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    costmap = Node(
        package="costmap_generator",
        executable="costmap_publisher",
        name="costmap__node",
        output="screen",
        emulate_tty=True,
    )

    camera_model = 'zed2i'
    zed_wrapper = IncludeLaunchDescription(
        launch_description_source=PythonLaunchDescriptionSource([
            get_package_share_directory('zed_wrapper'),
            '/launch/include/zed_camera.launch.py'
        ]),
        launch_arguments={
            'camera_model': camera_model,
            'ros_params_override_path': get_package_share_directory('costmap_generator') + '/config/override.yaml',
        }.items()
    )

    ld.add_action(zed_wrapper)
    ld.add_action(costmap)

    return ld
