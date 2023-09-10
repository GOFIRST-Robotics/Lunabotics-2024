ros2 run topic_tools relay /zed2i/zed_node/left/camera_info /camera/infra1/metadata & \
ros2 run topic_tools relay /zed2i/zed_node/right/camera_info /camera/infra2/metadata & \
ros2 run topic_tools relay /zed2i/zed_node/left/image_rect_color /camera/infra1/image_rect_raw & \
ros2 run topic_tools relay /zed2i/zed_node/right/image_rect_color /camera/infra2/image_rect_raw & \

ros2 run topic_tools relay /zed2i/zed_node/stereo/image_rect_color /camera/depth/image_rect_raw   & \
ros2 run topic_tools relay /zed2i/zed_node/depth/camera_info /camera/depth/metadata