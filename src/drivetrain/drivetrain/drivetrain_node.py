# This ROS 2 node contains code for the swerve drivetrain subsystem of the robot.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: October 2023

import math

# Import the ROS 2 module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import MotorCommandSet
from rovr_interfaces.srv import Stop, Drive


# This class represents an individual swerve module
class SwerveModule:
    def __init__(self, drive_motor, turning_motor, motor_set):
        self.drive_motor_can_id = drive_motor
        self.turning_motor_can_id = turning_motor
        self.cli_motor_set = motor_set

    def set_power(self, power: float) -> None:
        self.cli_motor_set.call_async(MotorCommandSet.Request(type="duty_cycle", value=power))

    def set_angle(self, angle: float) -> None:
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(
                type="position",
                value=angle,
            )
        )

    def get_absolute_angle(self) -> float:
        pass  # TODO: Implement this method for reading the absolute encoder (save this for later)

    def reset(self) -> None:
        pass  # TODO: Implement this method for resetting our relative encoder offset based on the absolute encoder (save this for later)

    def set_state(self, power: float, angle: float) -> None:
        self.set_angle(angle)
        self.set_power(power)


# This class represents the drivetrain as a whole (4 swerve modules)
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

        # Define default values for our ROS parameters below #
        self.declare_parameter("BACK_LEFT_DRIVE", 1)
        self.declare_parameter("BACK_LEFT_TURN", 2)
        self.declare_parameter("FRONT_LEFT_DRIVE", 3)
        self.declare_parameter("FRONT_LEFT_TURN", 4)
        self.declare_parameter("BACK_RIGHT_DRIVE", 5)
        self.declare_parameter("BACK_RIGHT_TURN", 6)
        self.declare_parameter("FRONT_RIGHT_DRIVE", 7)
        self.declare_parameter("FRONT_RIGHT_TURN", 8)
        self.declare_parameter("WHEEL_BASE", 0.5)
        self.declare_parameter("TRACK_WIDTH", 0.5)

        # Assign the ROS Parameters to member variables below #
        self.BACK_LEFT_DRIVE = self.get_parameter("BACK_LEFT_DRIVE").value
        self.BACK_LEFT_TURN = self.get_parameter("BACK_LEFT_TURN").value
        self.FRONT_LEFT_DRIVE = self.get_parameter("FRONT_LEFT_DRIVE").value
        self.FRONT_LEFT_TURN = self.get_parameter("FRONT_LEFT_TURN").value
        self.BACK_RIGHT_DRIVE = self.get_parameter("BACK_RIGHT_DRIVE").value
        self.BACK_RIGHT_TURN = self.get_parameter("BACK_RIGHT_TURN").value
        self.FRONT_RIGHT_DRIVE = self.get_parameter("FRONT_RIGHT_DRIVE").value
        self.FRONT_RIGHT_TURN = self.get_parameter("FRONT_RIGHT_TURN").value
        self.WHEEL_BASE = self.get_parameter("WHEEL_BASE").value
        self.TRACK_WIDTH = self.get_parameter("TRACK_WIDTH").value

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("BACK_LEFT_DRIVE has been set to: " + str(self.BACK_LEFT_DRIVE))
        self.get_logger().info("BACK_LEFT_TURN has been set to: " + str(self.BACK_LEFT_TURN))
        self.get_logger().info("FRONT_LEFT_DRIVE has been set to: " + str(self.FRONT_LEFT_DRIVE))
        self.get_logger().info("FRONT_LEFT_TURN has been set to: " + str(self.FRONT_LEFT_TURN))
        self.get_logger().info("BACK_RIGHT_DRIVE has been set to: " + str(self.BACK_RIGHT_DRIVE))
        self.get_logger().info("BACK_RIGHT_TURN has been set to: " + str(self.BACK_RIGHT_TURN))
        self.get_logger().info("FRONT_RIGHT_DRIVE has been set to: " + str(self.FRONT_RIGHT_DRIVE))
        self.get_logger().info("FRONT_RIGHT_TURN has been set to: " + str(self.FRONT_RIGHT_TURN))
        self.get_logger().info("WHEEL_BASE has been set to: " + str(self.WHEEL_BASE))
        self.get_logger().info("TRACK_WIDTH has been set to: " + str(self.TRACK_WIDTH))

        # Create each swerve module using
        self.back_left = SwerveModule(self.BACK_LEFT_DRIVE, self.BACK_LEFT_TURN, self.cli_motor_set)
        self.front_left = SwerveModule(self.FRONT_LEFT_DRIVE, self.FRONT_LEFT_TURN, self.cli_motor_set)
        self.back_right = SwerveModule(self.BACK_RIGHT_DRIVE, self.BACK_RIGHT_TURN, self.cli_motor_set)
        self.front_right = SwerveModule(self.FRONT_RIGHT_DRIVE, self.FRONT_RIGHT_TURN, self.cli_motor_set)

    # Define subsystem methods here
    def drive(self, forward_power: float, horizontal_power: float, turning_power: float) -> None:
        """This method drives the robot with the desired forward, horizontal, and turning power."""

        # Vector layouts = [Drive Power, Drive Direction(Degrees from forwards going counterclockwise)]

        # Intermediate equations to simplify future expressions
        A = horizontal_power - turning_power * self.WHEEL_BASE
        B = horizontal_power + turning_power * self.WHEEL_BASE
        C = forward_power - turning_power * self.TRACK_WIDTH
        D = forward_power + turning_power * self.TRACK_WIDTH

        # Gives the desired speed and angle for each module
        back_left_vector = [math.sqrt(A**2 + D**2), math.atan2(A, D) * 180 / math.pi]
        front_left_vector = [math.sqrt(B**2 + D**2), math.atan2(B, D) * 180 / math.pi]
        back_right_vector = [math.sqrt(A**2 + C**2), math.atan2(A, C) * 180 / math.pi]
        front_right_vector = [math.sqrt(B**2 + C**2), math.atan2(B, C) * 180 / math.pi]

        # Normalize wheel speeds if necessary
        largest_power = max([back_left_vector[0], front_left_vector[0], back_right_vector[0], front_right_vector[0]])
        if largest_power > 1.0:
            back_left_vector[0] = back_left_vector[0] / largest_power
            front_left_vector[0] = front_left_vector[0] / largest_power
            back_right_vector[0] = back_right_vector[0] / largest_power
            front_right_vector[0] = front_right_vector[0] / largest_power

        # TODO: optimize turning of the wheels (they should never need to turn more than 90 degrees)

        self.back_left.set_state(back_left_vector[0], back_left_vector[1])
        self.front_left.set_state(front_left_vector[0], front_left_vector[1])
        self.back_right.set_state(back_right_vector[0], back_right_vector[1])
        self.front_right.set_state(front_right_vector[0], front_right_vector[1])

    def stop(self) -> None:
        """This method stops the drivetrain."""
        self.drive(0.0, 0.0, 0.0)

    # Define service callback methods here
    def stop_callback(self, request, response):
        """This service request stops the drivetrain."""
        self.stop()
        response.success = 0  # indicates success
        return response

    def drive_callback(self, request, response):
        """This service request drives the robot with the specified speeds."""
        self.drive(request.forward_power, request.horizontal_power, request.turning_power)
        response.success = 0  # indicates success
        return response

    # Define subscriber callback methods here
    def cmd_vel_callback(self, msg: Twist) -> None:
        """This method is called whenever a message is received on the cmd_vel topic."""
        self.drive(msg.linear.y, msg.linear.x, msg.angular.z)


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
