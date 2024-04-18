import rclpy
from rclpy.node import Node

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nvblox_msgs.msg import DistanceMapSlice
import sys
import numpy as np
from PIL import Image

class compress_costmap(Node):
    def __init__(self):
        super().__init__('compress_costmap')
        
        self.nav2 = BasicNavigator()

       
        
        self.timer = self.create_timer(0.5, self.publish_costmap)

        # self.costmap_publisher = self.create_publisher(DistanceMapSlice, '/compressed_esdf', 10)

    def costmap_callback(self, msg):
        self.costmap = msg













    def publish_costmap(self):
        costmap = self.nav2.getGlobalCostmap()
        format = costmap.metadata
        res = format.resolution
        # print(sys.getsizeof(costmap.data))
        data = np.array(costmap.data).reshape((format.size_x, format.size_y))
        # print(data.shape)
        
        data = data[900:1100, 900:1100]
        data[data == 0] = 255
        # data = data[::4, ::4]
        # data = data.astype('uint8')
        # print(sys.getsizeof(data.flatten().tolist))
        print(sys.getsizeof(data.tolist()))
        print(type(data.flatten()))
        image = Image.fromarray(data.astype('uint8'))
        # Save the image
        image.save('matrix_image.png', quality=1)
        image2 = Image.open("matrix_image.png").convert("L")
        img_matrix = np.array(image2)
        print(sys.getsizeof(img_matrix.flatten()))
    


def main(args=None):
    rclpy.init(args=args)
    node = compress_costmap()
    node.get_logger().info("Combine ESDF node started")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()