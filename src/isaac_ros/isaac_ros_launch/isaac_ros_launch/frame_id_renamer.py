import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image


class FrameIDRenamer(Node):
    def __init__(self):
        super().__init__("frame_id_renamer")

        self.camera_info_subscription = self.create_subscription(CameraInfo, "/gazebo/color/camera_info", self.color_camera_info_callback, 10)
        self.camera_info_subscription = self.create_subscription(CameraInfo, "/gazebo/depth/camera_info", self.depth_camera_info_callback, 10)
        self.color_image_subscription = self.create_subscription(Image, "/gazebo/color/image", self.color_image_callback, 10)
        self.depth_image_subscription = self.create_subscription(Image, "/gazebo/depth/image", self.depth_image_callback, 10)

        self.color_camera_info_publisher = self.create_publisher(CameraInfo, "/color/camera_info", 10)
        self.depth_camera_info_publisher = self.create_publisher(CameraInfo, "/depth/camera_info", 10)
        self.color_image_publisher = self.create_publisher(Image, "/color/image", 10)
        self.depth_image_publisher = self.create_publisher(Image, "/depth/image", 10)
        #log statement
        self.get_logger().info("Frame ID Renamer node has been started")

    def color_camera_info_callback(self, msg):
        msg.header.frame_id = "zed2i_left_camera_optical_frame"
        self.color_camera_info_publisher.publish(msg)
    
    def depth_camera_info_callback(self, msg):
        msg.header.frame_id = "zed2i_left_camera_optical_frame"
        self.depth_camera_info_publisher.publish(msg)

    def color_image_callback(self, msg):
        msg.header.frame_id = "zed2i_left_camera_optical_frame"
        self.color_image_publisher.publish(msg)

    def depth_image_callback(self, msg):
        msg.header.frame_id = "zed2i_left_camera_optical_frame"
        self.depth_image_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    frame_id_renamer = FrameIDRenamer()
    rclpy.spin(frame_id_renamer)
    frame_id_renamer.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
