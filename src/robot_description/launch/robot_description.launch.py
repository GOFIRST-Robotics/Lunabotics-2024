from launch import LaunchDescription
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.descriptions import ParameterValue
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration


def generate_launch_description():

    # Launch Arguments
    setup_for_gazebo_arg = DeclareLaunchArgument(
        "setup_for_gazebo",
        default_value="False",
        description="Whether to run in gazebo",
    )

    pkg_project_description = get_package_share_directory("robot_description")
    # Load the SDF file from "description" package
    xacro_path = PathJoinSubstitution(
        [pkg_project_description, "models", "master_ASM", "urdf", "master_ASM.urdf.xacro"]
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[{"robot_description": ParameterValue(Command(["xacro", " ", xacro_path]), value_type=str)}],
    )

    jsp_node = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        output="both",
        condition=UnlessCondition(LaunchConfiguration("setup_for_gazebo")),
    )

    return LaunchDescription([setup_for_gazebo_arg, robot_state_publisher, jsp_node])
