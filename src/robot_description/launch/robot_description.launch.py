from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.descriptions import ParameterValue
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():

    pkg_project_description = get_package_share_directory("robot_description")
    # Load the SDF file from "description" package
    xacro_path = os.path.join(
        pkg_project_description, "models", "master_ASM", "urdf", "master_ASM.urdf.xacro"
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[
            {
                "robot_description": ParameterValue(
                    Command(["xacro", " ", xacro_path]), value_type=str
                )
            }
        ],
    )

    return LaunchDescription([robot_state_publisher])
