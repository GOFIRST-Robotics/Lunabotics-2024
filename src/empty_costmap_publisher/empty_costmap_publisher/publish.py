# Original Author: Benjamin Chen in Spring 2023
# Maintainer: Benjamin Chen
# Last Updated: May 2023

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, MapMetaData


class MinimalPublisher(Node):
    def __init__(self):
        super().__init__("minimal_publisher")
        self.declare_parameter("timer_period", 1)  # default value of the parameter (in seconds)
        # setup publisher to publish an OccupancyGrid to /map topic with queue size of 1 message
        self.publisher_ = self.create_publisher(OccupancyGrid, "map", 1)
        timer_period = self.get_parameter("timer_period").get_parameter_value().integer_value
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = OccupancyGrid(info=MapMetaData(width=3, height=3), data=[0, 0, 0, 0, -1, 0, 0, 0, 0])
        msg.header.frame_id = "/map"
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)
        self.i += 1


def main(args=None):
    rclpy.init(args=args)

    minimal_publisher = MinimalPublisher()

    rclpy.spin(minimal_publisher)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    minimal_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
