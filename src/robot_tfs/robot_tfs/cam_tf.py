import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist, Quaternion
from sensor_msgs.msg import Imu

from tf2_ros import TransformException
from tf2_ros.buffer import Buffer


class ImuListener(Node):
    def __init__(self):
        super().__init__("imu_tf2_frame_listener")

        self.tf_buffer = Buffer()

        self.target_frame = self.declare_parameter("target_frame", "camera_link").get_parameter_value().string_value

        self.imu_subscription = self.create_subscription(Imu, "imu/data", self.imu_listener_callback, 1)
        self.imu_subscription  # prevent unused variable warning

        self.publisher = self.create_publisher(Twist, "camera_link/base_link", 1)

    def imu_listener_callback(self, msg: Quaternion):
        self.get_logger().info("(IMU) x: %s y: %s z: %s" % (msg.orientation.x, msg.orientation.y, msg.orientation.z))

        from_frame_rel = self.target_frame
        to_frame_rel = "base_link"

        try:
            t = self.tf_buffer.lookup_transform(to_frame_rel, from_frame_rel, rclpy.time.Time())
        except TransformException as ex:
            self.get_logger().info(f"Could not transform {to_frame_rel} to {from_frame_rel}: {ex}")
            return

        relay = Twist()
        imu_orientation = msg.orientation
        translation_transform = t.transform.translation
        relay.linear.x, relay.linear.y, relay.linear.z = (
            translation_transform.x,
            translation_transform.y,
            translation_transform.z,
        )
        relay.angular.x, relay.angular.y, relay.angular.z = (
            imu_orientation.x,
            imu_orientation.y,
            imu_orientation.z,
        )

        self.publisher.publish(relay)


def main(args=None):
    rclpy.init(args=args)
    node = ImuListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


# listen for camera_link, imu/data, publish to base_link


if __name__ == "__main__":
    main()
