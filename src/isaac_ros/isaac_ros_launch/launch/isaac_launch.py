import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    bringup_dir = get_package_share_directory("isaac_ros_launch")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")
    apriltag_bringup_dir = get_package_share_directory("apriltag")

    # Launch Arguments
    run_rviz_arg = DeclareLaunchArgument("run_rviz", default_value="True", description="Whether to start RVIZ")
    setup_for_zed_arg = DeclareLaunchArgument(
        "setup_for_zed",
        default_value="True",
        description="Whether to run from live zed data",
    )
    setup_for_gazebo_arg = DeclareLaunchArgument(
        "setup_for_gazebo",
        default_value="False",
        description="Whether to run in gazebo",
    )
    use_nvblox_arg = DeclareLaunchArgument(
        "use_nvblox",
        default_value="True",
        description="Whether to run nvblox",
    )
    record_svo_arg = DeclareLaunchArgument(
        "record_svo",
        default_value="False",
        description="Whether to record a ZED svo file",
    )

    global_frame = LaunchConfiguration("global_frame", default="odom")

    # Create a shared container to hold composable nodes
    # for speed ups through intra process communication.
    shared_container_name = "shared_nvblox_container"
    shared_container = Node(
        name=shared_container_name,
        package="rclcpp_components",
        executable="component_container_mt",
        output="screen",
        condition=IfCondition(LaunchConfiguration("use_nvblox")),
    )

    # ZED
    zed_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(bringup_dir, "zed2i.launch.py")]),
        launch_arguments={
            "attach_to_shared_component_container": "True",
            "component_container_name": shared_container_name,
            "record_svo": LaunchConfiguration("record_svo"),
        }.items(),
        condition=IfCondition(LaunchConfiguration("setup_for_zed")),
    )
    # Gazebo
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                os.path.join(
                    get_package_share_directory("ros_gz_launch"),
                    "launch",
                    "UCF_field.launch.py",
                )
            ]
        ),
        condition=IfCondition(LaunchConfiguration("setup_for_gazebo")),
    )

    # Nvblox
    nvblox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(bringup_dir, "nvblox.launch.py")]),
        launch_arguments={
            "global_frame": global_frame,
            "setup_for_zed": LaunchConfiguration("setup_for_zed"),
            "setup_for_gazebo": LaunchConfiguration("setup_for_gazebo"),
            "attach_to_shared_component_container": "True",
            "component_container_name": shared_container_name,
        }.items(),
        condition=IfCondition(LaunchConfiguration("use_nvblox")),
    )

    # Rviz
    rviz_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                os.path.join(
                    bringup_dir,
                    "rviz.launch.py",
                )
            ]
        ),
        launch_arguments={
            "config_name": "zed_example.rviz",
            "global_frame": global_frame,
        }.items(),
        condition=IfCondition(LaunchConfiguration("run_rviz")),
    )

    # Nav2 params
    nav2_param_file = os.path.join("config", "nav2_isaac_sim.yaml")
    param_substitutions = {"global_frame": LaunchConfiguration("global_frame", default="odom")}
    configured_params = RewrittenYaml(
        source_file=nav2_param_file,
        root_key="",
        param_rewrites=param_substitutions,
        convert_types=True,
    )

    # nav2 launch
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup_dir, "launch", "navigation_launch.py")),
        launch_arguments={
            "use_sim_time": "False",
            "params_file": configured_params,
            "autostart": "True",
        }.items(),
    )

    # apriltag launch
    apriltag_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(apriltag_bringup_dir, "apriltag_launch.py")]),
        condition=UnlessCondition(LaunchConfiguration("setup_for_gazebo")),
    )
    # apriltag (gazebo) launch
    apriltag_gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(apriltag_bringup_dir, "apriltag_gazebo_launch.py")]),
        condition=IfCondition(LaunchConfiguration("setup_for_gazebo")),
    )

    return LaunchDescription(
        [
            run_rviz_arg,
            setup_for_zed_arg,
            setup_for_gazebo_arg,
            record_svo_arg,
            use_nvblox_arg,
            shared_container,
            nvblox_launch,
            nav2_launch,
            zed_launch,
            gazebo_launch,
            rviz_launch,
            apriltag_launch,
            apriltag_gazebo_launch,
        ]
    )
