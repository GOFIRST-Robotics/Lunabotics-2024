import math

from geometry_msgs.msg import TransformStamped

import numpy as np

import rclpy
from rclpy.node import Node
from scipy.spatial.transform import Rotation as R
from tf2_ros import TransformBroadcaster
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import tf2_ros

from nav_msgs.msg import Odometry


class FramePublisher(Node):

    def __init__(self):
        super().__init__("turtle_tf2_frame_publisher")

        # Initialize the transform broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscribe to a turtle{1}{2}/pose topic and call handle_turtle_pose
        # callback function on each message
        self.subscription = self.create_subscription(
            Odometry, "/zed2i/zed_node/odom", self.handle_odom_pose, 1
        )
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def handle_odom_pose(self, odom_msg: Odometry):
        odom_to_base_tf = TransformStamped()

        # Read message content and assign it to
        # corresponding tf variables
        odom_to_base_tf.header.stamp = self.get_clock().now().to_msg()
        odom_to_base_tf.header.frame_id = "odom"
        odom_to_base_tf.child_frame_id = "base_link"

        # since the odom frame is not the same as the camera frame, we need to get the transform between the two then apply it to the odom -> base_link transform
        base_to_camera_tf: TransformStamped = self.tf_buffer.lookup_transform(
            "base_link", "zed2i_camera_link", odom_to_base_tf.header.stamp
        )

        odom_to_base_tf.transform.translation.x = (
            odom_msg.pose.pose.position.x - base_to_camera_tf.transform.translation.x
        )
        odom_to_base_tf.transform.translation.y = (
            odom_msg.pose.pose.position.y - base_to_camera_tf.transform.translation.y
        )
        odom_to_base_tf.transform.translation.z = (
            odom_msg.pose.pose.position.z - base_to_camera_tf.transform.translation.z
        )

        # Transform the odom_msg orientation to the base_link frame
        odom_rot = R.from_quat(
            [
                odom_msg.pose.pose.orientation.x,
                odom_msg.pose.pose.orientation.y,
                odom_msg.pose.pose.orientation.z,
                odom_msg.pose.pose.orientation.w,
            ]
        )
        base_rot = R.from_quat(
            [
                base_to_camera_tf.transform.rotation.x,
                base_to_camera_tf.transform.rotation.y,
                base_to_camera_tf.transform.rotation.z,
                base_to_camera_tf.transform.rotation.w,
            ]
        )
        odom_tf_rot = odom_rot * base_rot.inv()
        odom_to_base_tf.transform.rotation.x = odom_tf_rot.as_quat()[0]
        odom_to_base_tf.transform.rotation.y = odom_tf_rot.as_quat()[1]
        odom_to_base_tf.transform.rotation.z = odom_tf_rot.as_quat()[2]
        odom_to_base_tf.transform.rotation.w = odom_tf_rot.as_quat()[3]

        # Send the transformation
        self.tf_broadcaster.sendTransform(odom_to_base_tf)


def main():
    rclpy.init()
    node = FramePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    rclpy.shutdown()
