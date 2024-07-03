from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    motor_control = Node(
        package="motor_control",
        executable="motor_control_node",
        name="motor_control_node",
        output="screen",
        emulate_tty=True,
    )

    ld.add_action(motor_control)

    return ld
