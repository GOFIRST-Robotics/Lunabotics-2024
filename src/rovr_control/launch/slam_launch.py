from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    zed_node = Node(
        package="zed_wrapper",
        executable="zed_wrapper",
        remappings=[
            ('/zed2i/zed_node/point_cloud/cloud_registered', '/point_cloud'),
            ('/zed2i/zed_node/rgb/image_rect_color', 'color/image'),
            ('/zed2i/zed_node/rgb/camera_info','color/camera_info'),
            ('/zed2i/zed_node/depth/camera_info','depth/camera_info'),
            ('/zed2i/zed_node/depth/depth_registered','depth/image'),
            ('/tf','transform'),
            ('/zed2i/zed_node/pose', '/pose'),
        ],
        parameters=["config/zed_common.yaml"]
    )
    
    ld.add_action(zed_node)

    return ld
