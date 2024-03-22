import launch
from launch_ros.actions import ComposableNodeContainer, Node
from launch_ros.descriptions import ComposableNode


def generate_launch_description():

    tag_reader = Node(
        package="apriltag",
        executable="apriltag_node",
        name="apriltag_node",
    )

    apriltag_node = ComposableNode(
        package="isaac_ros_apriltag",
        plugin="nvidia::isaac_ros::apriltag::AprilTagNode",
        name="isaac_ros_apriltag",
        namespace="",
        remappings=[("image", "camera")],
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
        remappings=[("image", "camera")],
    )

    apriltag_container = ComposableNodeContainer(
        package="rclcpp_components",
        name="apriltag_container",
        namespace="",
        executable="component_container_mt",
        composable_node_descriptions=[apriltag_node, image_format_converter_node_left],
        output="screen",
    )

    # Add nodes and containers to LaunchDescription
    return launch.LaunchDescription([tag_reader, apriltag_container])
