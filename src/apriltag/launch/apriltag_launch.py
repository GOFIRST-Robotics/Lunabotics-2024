import launch
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode


def generate_launch_description():

    tag_reader = Node(
        package="apriltag",
        executable="apriltag_node",
        name="apriltag_node",
        parameters=["config/rovr_control.yaml"],
    )

    isaac_ros_apriltag = ComposableNode(
        package="isaac_ros_apriltag",
        plugin="nvidia::isaac_ros::apriltag::AprilTagNode",
        name="isaac_ros_apriltag",
        namespace="",
        remappings=[
            ("image", "zed2i/zed_node/left/image_rect_color_rgb"),
            ("camera_info", "zed2i/zed_node/left/camera_info"),
        ],
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
        remappings=[
            ("image_raw", "zed2i/zed_node/left/image_rect_color"),
            ("image", "zed2i/zed_node/left/image_rect_color_rgb"),
        ],
    )

    apriltag_container = ComposableNodeContainer(
        package="rclcpp_components",
        name="apriltag_container",
        namespace="",
        executable="component_container_mt",
        composable_node_descriptions=[isaac_ros_apriltag, image_format_converter_node_left],
        output="screen",
    )

    # Add nodes and containers to LaunchDescription
    return launch.LaunchDescription([tag_reader, apriltag_container])
