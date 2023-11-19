from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()
    realsense = Node(
        package="realsense2_camera",
        executable="realsense2_camera_node",
        name="camera",
        namespace="skimmer"
        # remappings=[
        #     ('/camera/realsense2_camera/depth/image_rect_raw', '/depth/image_rect_raw'),
        #     ('/camera/camera/depth/image_rect_raw', '/depth/image_rect_raw'),
        #     ('/camera/depth/image_rect_raw', '/depth/image_rect_raw'),
        #     ('/depth/image_rect_raw', '/depth/image_rect_raw'),
        # ]
    )
    
    check_load = Node(
        package="skimmer",
        executable="ros_check_load",
        name="ros_check_load",
    )
    
    ld.add_action(realsense)
    ld.add_action(check_load)

    return ld