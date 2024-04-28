import os

from ament_index_python.packages import get_package_share_directory

import launch
from launch.substitutions import Command
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode


def generate_launch_description():

    tag_reader = Node(
        package="apriltag",
        executable="apriltag_node",
        name="apriltag_node",
        parameters=["config/rovr_control.yaml"],
    )

    apriltag_node = ComposableNode(
        package="isaac_ros_apriltag",
        plugin="nvidia::isaac_ros::apriltag::AprilTagNode",
        name="isaac_ros_apriltag",
        namespace="",
        remappings=[("image", "zed_node/left/image_rect_color_rgb"), ("camera_info", "zed_node/left/camera_info")],
    )

    image_format_converter_node_left = ComposableNode(
        package="isaac_ros_image_proc",
        plugin="nvidia::isaac_ros::image_proc::ImageFormatConverterNode",
        name="image_format_node_left",
        parameters=[
            {
                "encoding_desired": "rgb8",
            }
        ],
        remappings=[("image_raw", "zed_node/left/image_rect_color"), ("image", "zed_node/left/image_rect_color_rgb")],
    )

    apriltag_container = ComposableNodeContainer(
        package="rclcpp_components",
        name="apriltag_container",
        namespace="",
        executable="component_container_mt",
        composable_node_descriptions=[apriltag_node, image_format_converter_node_left],
        output="screen",
    )

    # The zed camera mode name. zed, zed2, zed2i, zedm, zedx or zedxm
    camera_model = "zed2i"

    # URDF/xacro file to be loaded by the Robot State Publisher node
    xacro_path = os.path.join(get_package_share_directory("zed_wrapper"), "urdf", "zed_descr.urdf.xacro")

    # ZED Configurations to be loaded by ZED Node
    config_common = os.path.join(get_package_share_directory("isaac_ros_apriltag"), "config", "zed.yaml")

    config_camera = os.path.join(get_package_share_directory("zed_wrapper"), "config", camera_model + ".yaml")

    # Robot State Publisher node
    rsp_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="zed_state_publisher",
        output="screen",
        parameters=[
            {
                "robot_description": Command(
                    ["xacro", " ", xacro_path, " ", "camera_name:=", camera_model, " ", "camera_model:=", camera_model]
                )
            }
        ],
    )

    # ZED node using manual composition
    zed_node = Node(
        package="zed_wrapper",
        executable="zed_wrapper",
        output="screen",
        parameters=[
            config_common,  # Common parameters
            config_camera,  # Camera related parameters
        ],
    )

    # Add nodes and containers to LaunchDescription
    return launch.LaunchDescription([tag_reader, apriltag_container, rsp_node, zed_node])
