from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    rovr_control = Node(
        package="rovr_control",
        executable="main_control_node",
        name="main_control_node",
        parameters=["config/rovr_control.yaml"],
        output="screen",
        emulate_tty=True,
    )

    motor_control = Node(
        package="motor_control",
        executable="motor_control_node",
        name="motor_control_node",
    )

    drivetrain = Node(
        package="drivetrain",
        executable="drivetrain_node",
        name="drivetrain_node",
    )
    conveyor = Node(
        package="conveyor",
        executable="conveyor_node",
        name="conveyor_node",
    )

    ld.add_action(rovr_control)
    ld.add_action(motor_control)
    ld.add_action(drivetrain)
    ld.add_action(conveyor)

    return ld
