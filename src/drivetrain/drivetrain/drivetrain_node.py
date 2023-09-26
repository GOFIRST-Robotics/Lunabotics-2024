# This ROS 2 node contains code for the drivetrain subsystem of the robot.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: September 2023

# Import the ROS 2 module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import MotorCommandSet
from rovr_interfaces.srv import Stop, Drive


class DrivetrainNode(Node):
    def __init__(self):
        """Initialize the ROS 2 drivetrain node."""
        super().__init__("drivetrain")

        # Define publishers and subscribers here
        self.cmd_vel_sub = self.create_subscription(Twist, "cmd_vel", self.cmd_vel_callback, 10)

        # Define service clients here
        self.cli_motor_set = self.create_client(MotorCommandSet, "motor/set")

        # Define services (methods callable from the outside) here
        self.srv_stop = self.create_service(Stop, "drivetrain/stop", self.stop_callback)
        self.srv_drive = self.create_service(Drive, "drivetrain/drive", self.drive_callback)

        # Define motor CAN IDs here
        self.FRONT_LEFT_DRIVE = 1
        self.BACK_LEFT_DRIVE = 4
        self.FRONT_RIGHT_DRIVE = 3
        self.BACK_RIGHT_DRIVE = 2

    # Define subsystem methods here
    def drive(self, forward_power, turning_power):
        """This method drives the robot with the desired forward power and turning power."""
        left_power = forward_power - turning_power
        right_power = forward_power + turning_power

        # Desaturate the wheel speeds if needed
        greater_input = max(abs(left_power), abs(right_power))
        if greater_input > 1.0:
            left_power /= greater_input
            right_power /= greater_input

        # Multiply power by -1 to invert motor direction
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.FRONT_LEFT_DRIVE, value=left_power * -1)
        )
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.BACK_LEFT_DRIVE, value=left_power * -1)
        )
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.FRONT_RIGHT_DRIVE, value=right_power * -1)
        )
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.BACK_RIGHT_DRIVE, value=right_power * -1)
        )

    def stop(self):
        """This method stops the drivetrain."""
        self.drive(0.0, 0.0)

    # Define service callback methods here
    def stop_callback(self, request, response) -> None:
        """This service request stops the drivetrain."""
        self.stop()
        response.success = 0  # indicates success
        return response

    def drive_callback(self, request, response) -> None:
        """This service request drives the robot with the specified speeds."""
        self.drive(request.forward_power, request.turning_power)
        response.success = 0  # indicates success
        return response

    # Define subscriber callback methods here
    def cmd_vel_callback(self, msg):
        """This method is called whenever a message is received on the cmd_vel topic."""
        self.drive(msg.linear.x, msg.angular.z)


def main(args=None):
    """The main function."""
    rclpy.init(args=args)

    node = DrivetrainNode()
    node.get_logger().info("Initializing the Drivetrain subsystem!")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
