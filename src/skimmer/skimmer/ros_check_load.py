import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge
import math
# import time

# TODO: NEED TO UPDATE SKIMMER SIZE, DISTANCE, DISTANCE THRESHOLD
# TODO: Should probably update pollrate/ consecutive cycles
# TODO: make sure hte topic names are all correct

SKIMMERSIZEY = 0.7112  # width of the skimmer in meters
SKIMMERSIZEX = 0.623  # length of the skimmer in meters
SKIMMERTOCAM = 0.3  # distance from camera to top of skimmer in meters.
DISTANCETHRESH = 200  # how small should the distance between top and skimmer be before offload (in meters)?
POLLRATE = 0.2  # Wait time between each distance check (in seconds)
CONSECUTIVECYCLES = 4  # Make sure the reading is consistent
skimmer_height_topic = "/skimmer/height"  # should be meters, as a displacement from the skimmers starting position, if not, convert


class ros_check_load(Node):
    def __init__(self):
        self.skimmer_height = .5
        self.img_height = 640
        self.errorCount = 0
        self.img_width = 848
        super().__init__("check_load")
        self.bridge = CvBridge()
        self.pub = self.create_publisher(Bool, "readyDump", 10)
        self.prior_checks = []
        depth_image_topic = "/skimmer/camera/depth/image_rect_raw"  # The launch file should remap so the realsense publishes to this topic
        self.getSkimmerHeight = self.create_subscription(Float32, skimmer_height_topic, self.setHeight, 10)
        self.oneTimeSub = self.create_subscription(Image, depth_image_topic, self.setParamCallback, 10)
        self.subscriber = self.create_subscription(Image, depth_image_topic, self.depth_image_callback, 10)
        self.timer = self.create_timer(POLLRATE, self.publish_distance)
        self.depth_image = None
        

    def setHeight(self, msg):
        """Sets the height of the skimmer belt to a variable."""
        self.skimmer_height = msg.data

    def setParamCallback(self, msg):
        """Sets the image height and width parameters for the camera.
        One time callback, kills itself after it's done."""
        self.img_height = msg.height
        self.img_width = msg.width
        self.destroy_subscription(self.oneTimeSub)

    def depth_image_callback(self, msg):
        """Callback for the depth image. Sets the depth image to the class variable, as a cv2 image."""
        self.depth_image = self.bridge.imgmsg_to_cv2(msg, msg.encoding)

    def publish_distance(self):
        """does the actual math to determine if the skimmer is ready to offload. Publishes a bool to the readyDump topic.
        Called every POLLRATE seconds.
        Will kill the node after 5 seconds of not receiving a depth image / throwing consecutive errors."""
        if self.depth_image is None:
            self.get_logger().fatal(f"Camera not working")
            self.get_logger().fatal("Killing check_load node")
            self.destroy_node()
            return
        
        """Cropping the image"""
        depth = self.depth_image

        # find the degrees of vision occupied by the skimmer belt
        perceptionChangeX = (
            (2 * (math.atan((0.5 * SKIMMERSIZEX) / (self.skimmer_height + SKIMMERTOCAM)))) * (180 / math.pi)
        )
        perceptionChangeY = (
            (2 * (math.atan((0.5 * SKIMMERSIZEY) / (self.skimmer_height + SKIMMERTOCAM)))) * (180 / math.pi)
        )

        percentFOVx = min(perceptionChangeX / 86, 1)
        # compare the degrees of vision it would occupy to the FOV of the realsense
        percentFOVy = min(perceptionChangeY / 57, 1)

        change_x = (
            int(self.img_width * percentFOVx / 2)
        )   # get the number of pixels that it's occupying. divide by 2 so it's a +- situation
        change_y = int((self.img_height * percentFOVy) / 2)

        center_x, center_y = self.img_width // 2, self.img_height // 2
        denoised_image = cv2.GaussianBlur(depth, (5, 5), 0)
        resized_img = denoised_image[center_y - change_y : center_y + change_y, center_x - change_x : center_x + change_x]

        """Analyzing image, posting to topic"""
        if resized_img.mean() <= DISTANCETHRESH + self.skimmer_height:
            self.prior_checks.append(True)
        else:
            self.prior_checks.append(False)

        if len(self.prior_checks) >= CONSECUTIVECYCLES:
            self.prior_checks.pop(0)
            msg = Bool()
            if False not in self.prior_checks:
                msg.data = True
            else:
                msg.data = False
            self.errorCount = 0
            self.pub.publish(msg)
            self.depth_image = None


def main(args=None):
    """The main function."""
    rclpy.init(args=args)
    
    node = ros_check_load()
    node.get_logger().info("Starting the depth camera for check_load")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
