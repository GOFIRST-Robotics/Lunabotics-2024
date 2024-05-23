from launch_ros.substitutions import FindPackageShare

from launch_ros.actions import Node
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    ld = LaunchDescription()

    main_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("rovr_control"), "main_no_joysticks_launch.py"])
        )
    )

    isaac_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([FindPackageShare("isaac_ros_launch"), "isaac_launch.py"])),
        launch_arguments={
            "setup_for_zed": "True",
            "setup_for_gazebo": "False",
            "use_nvblox": "True",
            "run_rviz_robot": "False",  # We don't need to run RViz during matches
            "record_svo": "True",  # Record match data to an SVO file
        }.items(),
    )

    gstreamer_server = Node(
        package="gstreamer",
        executable="server_node",
        name="gstreamer_server_node",
        output="screen",
        emulate_tty=True,
    )

    # Add all of the actions to the launch description
    ld.add_action(main_launch)
    ld.add_action(gstreamer_server)
    ld.add_action(isaac_launch)

    # Return the launch description
    return ld
