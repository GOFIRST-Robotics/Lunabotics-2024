import rclpy
from rclpy.node import Node

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

from nvblox_msgs.msg import DistanceMapSlice
import numpy as np

class compress_costmap(Node):
    def __init__(self):
        super().__init__('compress_costmap')
        
        self.nav2 = BasicNavigator()

        # self.nav2.waitUntilNav2Active()

        print(self.nav2.getFeedback())

        # self.costmap_subscriber = self.create_subscription(
        #     DistanceMapSlice,
        #     '/combined_esdf',
        #     self.costmap_callback,
        #     10)
        
        # self.costmap = None
        
        # self.timer = self.create_timer(0.5, self.publish_costmap)

        # self.costmap_publisher = self.create_publisher(DistanceMapSlice, '/compressed_esdf', 10)

    def costmap_callback(self, msg):
        self.costmap = msg
    


def main(args=None):
    rclpy.init(args=args)
    node = compress_costmap()
    node.get_logger().info("Combine ESDF node started")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()