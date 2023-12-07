import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16, Bool
import serial
import struct
import time


class read_serial(Node):
    def __init__(self):
        super().__init__("read_serial")
        self.frontLeftEncoder = self.create_publisher(Int16, "frontLeftEncoder", 10)
        self.frontRightEncoder = self.create_publisher(Int16, "frontRightEncoder", 10)
        self.backLeftEncoder = self.create_publisher(Int16, "backLeftEncoder", 10)
        self.backRightEncoder = self.create_publisher(Int16, "backRightEncoder", 10)
        self.topLimitSwitch = self.create_publisher(Int16, "topLimitSwitch", 10)
        self.bottomLimitSwitch = self.create_publisher(Int16, "bottomLimitSwitch", 10)
        try:
            self.arduino = serial.Serial("/dev/name", 9600)  # TODO change the name of the arduino
            time.sleep(1)  # https://stackoverflow.com/questions/7266558/pyserial-buffer-wont-flush
            self.arduino.read_all()
        except Exception as e:
            self.get_logger().fatal(f"Error connecting to serial: {e}")
            self.destroy_node()
            return

        while True:
            if self.arduino is None:
                self.get_logger().fatal("Killing read_serial node")
                self.destroy_node()
                return
            data = self.arduino.read(10)  # Pause until 10 bytes are read
            decoded = struct.unpack("??hhhh", data)  # Use h for each int because arduino int is 2 bytes

            msg = Int16()
            msg.data = decoded[0]
            self.frontLeftEncoder.publish(msg)
            msg.data = decoded[1]
            self.frontRightEncoder.publish(msg)
            msg.data = decoded[2]
            self.backLeftEncoder.publish(msg)
            msg.data = decoded[3]
            self.backRightEncoder.publish(msg)
            msg = Bool()
            msg.data = decoded[4]
            self.topLimitSwitch.publish(msg)
            msg.data = decoded[5]
            self.bottomLimitSwitch.publish(msg)


def main(args=None):
    """The main function."""
    rclpy.init(args=args)

    node = read_serial()
    node.get_logger().info("Starting serial reader")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
