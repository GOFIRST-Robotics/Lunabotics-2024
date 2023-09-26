# This ROS 2 node contains code for the digger subsystem of the robot.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: September 2023

# Import the ROS 2 Python module
import rclpy
from rclpy.node import Node

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import MotorCommandSet
from rovr_interfaces.srv import SetPower, Stop


class DiggerNode(Node):
    def __init__(self):
        """Initialize the ROS 2 digger node."""
        super().__init__("digger")

        # Define service clients here
        self.cli_motor_set = self.create_client(MotorCommandSet, "motor/set")

        # Define services (methods callable from the outside) here
        self.srv_toggle = self.create_service(SetPower, "digger/toggle", self.toggle_callback)
        self.srv_stop = self.create_service(Stop, "digger/stop", self.stop_callback)
        self.srv_setPower = self.create_service(SetPower, "digger/setPower", self.set_power_callback)

        # Define motor CAN IDs here
        self.DIGGER = 8

        # Current subsystem state
        self.running = False

    # Define subsystem methods here
    def set_power(self, power: float) -> None:
        """This method sets power to the digging drum."""
        self.running = True
        self.cli_motor_set.call_async(MotorCommandSet.Request(type="duty_cycle", can_id=self.DIGGER, value=power))

    def stop(self) -> None:
        """This method stops the digging drum."""
        self.running = False
        self.cli_motor_set.call_async(MotorCommandSet.Request(type="duty_cycle", can_id=self.DIGGER, value=0.0))

    def toggle(self, power: float) -> None:
        """This method toggles the digging drum."""
        if self.running:
            self.stop()
        else:
            self.set_power(power)

    # Define service callback methods here
    def set_power_callback(self, request, response) -> None:
        """This service request sets power to the digging drum."""
        self.set_power(request.power)
        response.success = 0  # indicates success
        return response

    def stop_callback(self, request, response) -> None:
        """This service request stops the digging drum."""
        self.stop()
        response.success = 0  # indicates success
        return response

    def toggle_callback(self, request, response) -> None:
        """This service request toggles the digging drum."""
        self.toggle(request.power)
        response.success = 0  # indicates success
        return response


def main(args=None):
    """The main function."""
    rclpy.init(args=args)

    node = DiggerNode()
    node.get_logger().info("Initializing the Digger subsystem!")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
