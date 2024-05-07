from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess


# Launches the joystick node and the gstreamer camera client on the operator laptop
def generate_launch_description():
    ld = LaunchDescription()

    joystick_node = Node(
        package="joy",
        executable="joy_node",
        parameters=["config/joy_node.yaml"],
    )

    start_gStreamer_client = ExecuteProcess(
        cmd=["rqt", "--force-discover", "--standalone", "CameraClient"], shell=True, output="screen"
    )

    ld.add_action(joystick_node)
    ld.add_action(start_gStreamer_client)

    return ld
