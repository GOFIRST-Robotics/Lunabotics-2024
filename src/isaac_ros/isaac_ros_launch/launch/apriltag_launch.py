from launch import LaunchDescription
from launch_ros.descriptions import ComposableNode
from launch_ros.actions import ComposableNodeContainer


def generate_launch_description():
    ld = LaunchDescription()

    apriltag_node = ComposableNode(
        package="isaac_ros_apriltag",
        plugin="nvidia::isaac_ros::apriltag::AprilTagNode",
        name="apriltag",
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

    # Add the action to the launch description
    ld.add_action(apriltag_container)

    # Return the launch description
    return ld
