# import os
from launch import LaunchDescription
# from launch_ros.actions import Node
from launch.actions import ExecuteProcess
# from launch.conditions import IfCondition
# from launch.actions import DeclareLaunchArgument
# from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

# Launches the joystick node and the gstreamer camera client on the operator laptop
def generate_launch_description():
    ld = LaunchDescription()

    # bringup_dir = os.path.join("config", "rviz")

    # # Config
    # config_name = LaunchConfiguration("config_name", default="zed_example.rviz")
    # config_path = PathJoinSubstitution([bringup_dir, config_name])
    # global_frame = LaunchConfiguration("global_frame", default="map")

    # run_rviz_arg = DeclareLaunchArgument("run_rviz_client", default_value="True", description="Whether to start RVIZ")

    # joystick_node = Node(
    #     package="joy",
    #     executable="joy_node",
    #     parameters=["config/joy_node.yaml"],
    # )

    start_gStreamer_client = ExecuteProcess(
        cmd=["rqt", "--force-discover", "--standalone", "CameraClient"], shell=True, output="screen"
    )

    # rviz_node = Node(
    #     package="rviz2",
    #     executable="rviz2",
    #     name="rviz2",
    #     output="screen",
    #     arguments=["-d", config_path, "-f", global_frame],
    #     condition=IfCondition(LaunchConfiguration("run_rviz_client")),
    # )

    # ld.add_action(run_rviz_arg)
    # ld.add_action(joystick_node) # TODO: The joystick node currently does not work inside the container
    ld.add_action(start_gStreamer_client)
    # ld.add_action(rviz_node)

    return ld
