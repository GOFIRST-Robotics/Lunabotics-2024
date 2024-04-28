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

    apriltag_node = ComposableNode(
        package="isaac_ros_apriltag",
        plugin="nvidia::isaac_ros::apriltag::AprilTagNode",
        name="isaac_ros_apriltag",
        namespace="",
        remappings=[("image", "color_camera_image"), ("camera_info", "color_camera_info")],
    )

    apriltag_container = ComposableNodeContainer(
        package="rclcpp_components",
        name="apriltag_container",
        namespace="",
        executable="component_container_mt",
        composable_node_descriptions=[apriltag_node],
        output="screen",
    )

    # Add nodes and containers to LaunchDescription
    return launch.LaunchDescription([tag_reader, apriltag_container])
