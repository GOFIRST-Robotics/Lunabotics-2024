import rclpy
from rclpy.node import Node
from rovr_interfaces.msg import LimitSwitches, AbsoluteEncoders

import serial
import struct
import time


class read_serial(Node):
    def __init__(self):
        super().__init__("read_serial")

        self.limitSwitchesPub = self.create_publisher(LimitSwitches, "limitSwitches", 10)
        self.absoluteEncodersPub = self.create_publisher(AbsoluteEncoders, "absoluteEncoders", 10)

        try:
            self.arduino = serial.Serial("/dev/Arduino", 9600)  # This should be a static serial port on the Jetson!
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

            msg = LimitSwitches()
            msg.top_limit_switch = decoded[0]
            msg.bottom_limit_switch = decoded[1]
            self.limitSwitchesPub.publish(msg)

            msg = AbsoluteEncoders()
            msg.front_left_encoder = decoded[2]
            msg.front_right_encoder = decoded[3]
            msg.back_left_encoder = decoded[4]
            msg.back_right_encoder = decoded[5]
            self.absoluteEncodersPub.publish(msg)


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
