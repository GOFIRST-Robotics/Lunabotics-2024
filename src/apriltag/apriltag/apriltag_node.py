from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from isaac_ros_apriltag_interfaces.msg import AprilTagDetectionArray
import xml.etree.ElementTree as ET
import os

"""Make sure to turn on the camera using 
ros2 launch isaac_ros_apriltag isaac_ros_apriltag_usb_cam.launch.py
or nothing here will work"""


class ApriltagNode(Node):
    def __init__(self):
        super().__init__("apriltag_node")
        current_dir = os.getcwd()

        """Change this based on the field."""
        relative_path = "src/apriltag/apriltag/apriltag_location_nasa.urdf.xarco"
        # relative_path = "src/apriltag/apriltag/apriltag_location_ucf.urdf.xarco"

        self.file_path = os.path.join(current_dir, relative_path)
        self.transforms = self.create_subscription(AprilTagDetectionArray, "/tag_detections", self.sendTransform, 10)
        self.tf_broadcaster = TransformBroadcaster(self)

    def printTransforms(self, msg):
        if len(msg.detections) == 0:
            return
        home = msg.detections[0]
        print(home.pose.pose.pose.position.x)
        print(home.pose.pose.pose.position.y)
        print(home.pose.pose.pose.position.z)

    def sendTransform(self, msg):
        if len(msg.detections) == 0:
            return

        tag = msg.detections[0]
        t = TransformStamped()
        t.child_frame_id = "odom"
        t.header.frame_id = "map"
        t.header.stamp = self.get_clock().now().to_msg()
        self.makeTransforms(t, tag)

        # While this is only being used for a start transform.
        # probably shouldnt kill itself if we want to keep publishing transforms
        self.destroy_node()
        return

    def makeTransforms(self, t, tag):
        id = tag.id
        tree = ET.parse(self.file_path)
        root = tree.getroot()

        link = root[id - 1]  # assumes tag 1 = home 1, tag 2 = home 2, 3 = berm 1 etc.

        xyz_elements = link.findall(".//origin[@xyz]")
        xyz_values = [element.attrib["xyz"] for element in xyz_elements]
        xyz = xyz_values[0].split(" ")

        rpy_elements = link.findall(".//origin[@rpy]")
        rpy_values = [element.attrib["rpy"] for element in rpy_elements]
        rpy = rpy_values[0].split(" ")

        t.transform.translation.x = tag.pose.pose.pose.position.x - float(xyz[0])
        t.transform.translation.y = tag.pose.pose.pose.position.z - float(xyz[1])
        t.transform.translation.z = tag.pose.pose.pose.position.y - float(xyz[2])
        t.transform.rotation.x = tag.pose.pose.pose.orientation.x - float(rpy[0])
        t.transform.rotation.y = tag.pose.pose.pose.orientation.y - float(rpy[1])
        t.transform.rotation.z = tag.pose.pose.pose.orientation.z - float(rpy[2])
        self.tf_broadcaster.sendTransform(t)


def main(args=None):
    """The main function."""
    rclpy.init(args=args)

    node = ApriltagNode()
    node.get_logger().info("Initializing the Apriltag node!")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()
