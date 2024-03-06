# This ROS 2 node contains code for the swerve drivetrain subsystem of the robot.
# Original Author: Akshat Arinav <arina004@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: February 2024 by Anthony Brogni

import math

# Import the ROS 2 module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import Stop, Drive, MotorCommandSet
from rovr_interfaces.msg import AbsoluteEncoders


# This class represents an individual swerve module
class SwerveModule:
    def __init__(self, drive_motor, turning_motor, drivetrain):
        self.drive_motor_can_id = drive_motor
        self.turning_motor_can_id = turning_motor
        self.cli_motor_set = drivetrain.cli_motor_set
        self.steering_motor_gear_ratio = drivetrain.STEERING_MOTOR_GEAR_RATIO
        self.encoder_offset = 0
        self.current_absolute_angle = None
        self.gazebo_wheel = None
        self.gazebo_swerve = None
        self.simulation = drivetrain.GAZEBO_SIMULATION
        self.prev_angle = 0.0

    def set_power(self, power: float) -> None:
        self.cli_motor_set.call_async(MotorCommandSet.Request(type="duty_cycle", value=power))

    def set_angle(self, angle: float) -> None:
        self.cli_motor_set.call_async(MotorCommandSet.Request(type="position", value=(angle - self.encoder_offset) * self.steering_motor_gear_ratio))

    def reset(self, current_relative_angle) -> None:
        self.encoder_offset = self.current_absolute_angle - current_relative_angle 
        print("Absolute Encoder angle offset set to:", self.encoder_offset)
        self.set_angle(0)  # Rotate the module to the 0 degree position

    def set_state(self, power: float, angle: float) -> None:
        self.set_angle(angle)
        self.set_power(power)
        if self.simulation:
            self.publish_gazebo(power, angle)

    def set_gazebo_pubs(self, wheel, swerve):
        self.gazebo_wheel = wheel
        self.gazebo_swerve = swerve

    def publish_gazebo(self, power: float, angle: float) -> None:
        # Convert from counterclockwise -> clockwise
        angle = (360 - angle) % 360
        # Convert from degrees to radians
        rad = angle * math.pi / 180

        speed = power * 5
        self.gazebo_wheel.publish(Float64(data = speed))
        self.gazebo_swerve.publish(Float64(data = rad))



# This class represents the drivetrain as a whole (4 swerve modules)
class DrivetrainNode(Node):
    def __init__(self):
        """Initialize the ROS 2 drivetrain node."""
        super().__init__("drivetrain")

        # Define default values for our ROS parameters below #
        self.declare_parameter("FRONT_LEFT_DRIVE", 3)
        self.declare_parameter("FRONT_LEFT_TURN", 4)
        self.declare_parameter("FRONT_RIGHT_DRIVE", 7)
        self.declare_parameter("FRONT_RIGHT_TURN", 8)
        self.declare_parameter("BACK_LEFT_DRIVE", 1)
        self.declare_parameter("BACK_LEFT_TURN", 2)
        self.declare_parameter("BACK_RIGHT_DRIVE", 5)
        self.declare_parameter("BACK_RIGHT_TURN", 6)
        self.declare_parameter("HALF_WHEEL_BASE", 0.5)
        self.declare_parameter("HALF_TRACK_WIDTH", 0.5)
        self.declare_parameter("STEERING_MOTOR_GEAR_RATIO", 20)
        self.declare_parameter("FRONT_LEFT_MAGNET_OFFSET", 0)
        self.declare_parameter("FRONT_RIGHT_MAGNET_OFFSET", 0)
        self.declare_parameter("BACK_LEFT_MAGNET_OFFSET", 0)
        self.declare_parameter("BACK_RIGHT_MAGNET_OFFSET", 0)
        self.declare_parameter("GAZEBO_SIMULATION", False)

        # Assign the ROS Parameters to member variables below #
        self.FRONT_LEFT_DRIVE = self.get_parameter("FRONT_LEFT_DRIVE").value
        self.FRONT_LEFT_TURN = self.get_parameter("FRONT_LEFT_TURN").value
        self.FRONT_RIGHT_DRIVE = self.get_parameter("FRONT_RIGHT_DRIVE").value
        self.FRONT_RIGHT_TURN = self.get_parameter("FRONT_RIGHT_TURN").value
        self.BACK_LEFT_DRIVE = self.get_parameter("BACK_LEFT_DRIVE").value
        self.BACK_LEFT_TURN = self.get_parameter("BACK_LEFT_TURN").value
        self.BACK_RIGHT_DRIVE = self.get_parameter("BACK_RIGHT_DRIVE").value
        self.BACK_RIGHT_TURN = self.get_parameter("BACK_RIGHT_TURN").value
        self.HALF_WHEEL_BASE = self.get_parameter("HALF_WHEEL_BASE").value
        self.HALF_TRACK_WIDTH = self.get_parameter("HALF_TRACK_WIDTH").value
        self.STEERING_MOTOR_GEAR_RATIO = self.get_parameter("STEERING_MOTOR_GEAR_RATIO").value
        self.FRONT_LEFT_MAGNET_OFFSET = self.get_parameter("FRONT_LEFT_MAGNET_OFFSET").value
        self.FRONT_RIGHT_MAGNET_OFFSET = self.get_parameter("FRONT_RIGHT_MAGNET_OFFSET").value
        self.BACK_LEFT_MAGNET_OFFSET = self.get_parameter("BACK_LEFT_MAGNET_OFFSET").value
        self.BACK_RIGHT_MAGNET_OFFSET = self.get_parameter("BACK_RIGHT_MAGNET_OFFSET").value
        self.GAZEBO_SIMULATION = self.get_parameter("GAZEBO_SIMULATION").value

        # Define publishers and subscribers here
        self.cmd_vel_sub = self.create_subscription(Twist, "cmd_vel", self.cmd_vel_callback, 10)
        self.absolute_encoders_sub = self.create_subscription(AbsoluteEncoders, "absoluteEncoders", self.absolute_encoders_callback, 10)

        if self.GAZEBO_SIMULATION:
            self.gazebo_wheel1_pub = self.create_publisher(Float64, "wheel1/cmd_vel", 10)
            self.gazebo_wheel2_pub = self.create_publisher(Float64, "wheel2/cmd_vel", 10)
            self.gazebo_wheel3_pub = self.create_publisher(Float64, "wheel3/cmd_vel", 10)
            self.gazebo_wheel4_pub = self.create_publisher(Float64, "wheel4/cmd_vel", 10)
            self.gazebo_swerve1_pub = self.create_publisher(Float64, "swerve1/cmd_pos", 10)
            self.gazebo_swerve2_pub = self.create_publisher(Float64, "swerve2/cmd_pos", 10)
            self.gazebo_swerve3_pub = self.create_publisher(Float64, "swerve3/cmd_pos", 10)
            self.gazebo_swerve4_pub = self.create_publisher(Float64, "swerve4/cmd_pos", 10)         

        # Define service clients here
        self.cli_motor_set = self.create_client(MotorCommandSet, "motor/set")

        # Define services (methods callable from the outside) here
        self.srv_stop = self.create_service(Stop, "drivetrain/stop", self.stop_callback)
        self.srv_drive = self.create_service(Drive, "drivetrain/drive", self.drive_callback)

        # Define timers here
        self.absolute_angle_timer = self.create_timer(0.05, self.absolute_angle_reset)

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("FRONT_LEFT_DRIVE has been set to: " + str(self.FRONT_LEFT_DRIVE))
        self.get_logger().info("FRONT_LEFT_TURN has been set to: " + str(self.FRONT_LEFT_TURN))
        self.get_logger().info("FRONT_RIGHT_DRIVE has been set to: " + str(self.FRONT_RIGHT_DRIVE))
        self.get_logger().info("FRONT_RIGHT_TURN has been set to: " + str(self.FRONT_RIGHT_TURN))
        self.get_logger().info("BACK_LEFT_DRIVE has been set to: " + str(self.BACK_LEFT_DRIVE))
        self.get_logger().info("BACK_LEFT_TURN has been set to: " + str(self.BACK_LEFT_TURN))
        self.get_logger().info("BACK_RIGHT_DRIVE has been set to: " + str(self.BACK_RIGHT_DRIVE))
        self.get_logger().info("BACK_RIGHT_TURN has been set to: " + str(self.BACK_RIGHT_TURN))
        self.get_logger().info("HALF_WHEEL_BASE has been set to: " + str(self.HALF_WHEEL_BASE))
        self.get_logger().info("HALF_TRACK_WIDTH has been set to: " + str(self.HALF_TRACK_WIDTH))
        self.get_logger().info("STEERING_MOTOR_GEAR_RATIO has been set to: " + str(self.STEERING_MOTOR_GEAR_RATIO))
        self.get_logger().info("FRONT_LEFT_MAGNET_OFFSET has been set to: " + str(self.FRONT_LEFT_MAGNET_OFFSET))
        self.get_logger().info("FRONT_RIGHT_MAGNET_OFFSET has been set to: " + str(self.FRONT_RIGHT_MAGNET_OFFSET))
        self.get_logger().info("BACK_LEFT_MAGNET_OFFSET has been set to: " + str(self.BACK_LEFT_MAGNET_OFFSET))
        self.get_logger().info("BACK_RIGHT_MAGNET_OFFSET has been set to: " + str(self.BACK_RIGHT_MAGNET_OFFSET))
        self.get_logger().info("GAZEBO_SIMULATION has been set to: " + str(self.GAZEBO_SIMULATION))

        # Create each swerve module using
        self.front_left = SwerveModule(self.FRONT_LEFT_DRIVE, self.FRONT_LEFT_TURN, self)
        self.front_right = SwerveModule(self.FRONT_RIGHT_DRIVE, self.FRONT_RIGHT_TURN, self)
        self.back_left = SwerveModule(self.BACK_LEFT_DRIVE, self.BACK_LEFT_TURN, self)
        self.back_right = SwerveModule(self.BACK_RIGHT_DRIVE, self.BACK_RIGHT_TURN, self)

        if self.GAZEBO_SIMULATION:
            self.front_left.set_gazebo_pubs(self.gazebo_wheel1_pub, self.gazebo_swerve1_pub)
            self.front_right.set_gazebo_pubs(self.gazebo_wheel3_pub, self.gazebo_swerve3_pub)
            self.back_left.set_gazebo_pubs(self.gazebo_wheel4_pub, self.gazebo_swerve4_pub)
            self.back_right.set_gazebo_pubs(self.gazebo_wheel2_pub, self.gazebo_swerve2_pub)

    def absolute_angle_reset(self):
        # self.front_left was chosen arbitrarily
        if self.front_left.current_absolute_angle is not None:
            print("Absolute Encoder angles reset")
            self.front_left.reset(0)
            self.front_right.reset(0)
            self.back_left.reset(0) 
            self.back_right.reset(0)
            self.absolute_angle_timer.cancel()

    # Define subsystem methods here
    def drive(self, forward_power: float, horizontal_power: float, turning_power: float) -> None:
        """This method drives the robot with the desired forward, horizontal and turning power."""

        # flip turning direction
        turning_power *= -1  # TODO: Will this be wrong on the real robot?

        # Do not change the angle of the modules if the robot is being told to stop
        if abs(forward_power) < 0.05 and abs(horizontal_power) < 0.05 and abs(turning_power) < 0.05:
            self.front_left.set_state(0.0, self.front_left.prev_angle)
            self.front_right.set_state(0.0, self.front_right.prev_angle)
            self.back_left.set_state(0.0, self.back_left.prev_angle)
            self.back_right.set_state(0.0, self.back_right.prev_angle)
            return

        # Vector layouts = [Drive Power, Drive Direction(Degrees from forwards going counterclockwise)]
        # Intermediate equations to simplify future expressions
        A = horizontal_power - turning_power * self.HALF_WHEEL_BASE
        B = horizontal_power + turning_power * self.HALF_WHEEL_BASE
        C = forward_power - turning_power * self.HALF_TRACK_WIDTH
        D = forward_power + turning_power * self.HALF_TRACK_WIDTH

        # Gives the desired speed and angle for each module
        # Note: Angle has range from 0 to 360 degrees to make future calculations easier
        front_left_vector = [math.sqrt(B**2 + D**2), ((math.atan2(B, D) * 180 / math.pi) + 360) % 360]
        front_right_vector = [math.sqrt(B**2 + C**2), ((math.atan2(B, C) * 180 / math.pi) + 360) % 360]
        back_left_vector = [math.sqrt(A**2 + D**2), ((math.atan2(A, D) * 180 / math.pi) + 360) % 360]
        back_right_vector = [math.sqrt(A**2 + C**2), ((math.atan2(A, C) * 180 / math.pi) + 360) % 360]

        # Normalize wheel speeds if necessary
        largest_power = max([abs(front_left_vector[0]), abs(front_right_vector[0]), abs(back_left_vector[0]), abs(back_right_vector[0])])
        if largest_power > 1.0:
            front_left_vector[0] = front_left_vector[0] / largest_power
            front_right_vector[0] = front_right_vector[0] / largest_power
            back_left_vector[0] = back_left_vector[0] / largest_power
            back_right_vector[0] = back_right_vector[0] / largest_power

        # Note: no module should ever have to rotate more than 90 degrees from its current angle
        if abs(front_left_vector[1] - self.front_left.prev_angle) > 90 and abs(front_left_vector[1] - self.front_left.prev_angle) < 270:
            front_left_vector[1] = (front_left_vector[1] + 180) % 360
            # reverse speed of the module
            front_left_vector[0] = front_left_vector[0] * -1
        if abs(front_right_vector[1] - self.front_right.prev_angle) > 90 and abs(front_right_vector[1] - self.front_right.prev_angle) < 270:
            front_right_vector[1] = (front_right_vector[1] + 180) % 360
            # reverse speed of the module
            front_right_vector[0] = front_right_vector[0] * -1
        if abs(back_left_vector[1] - self.back_left.prev_angle) > 90 and abs(back_left_vector[1] - self.back_left.prev_angle) < 270:
            back_left_vector[1] = (back_left_vector[1] + 180) % 360
            # reverse speed of the module
            back_left_vector[0] = back_left_vector[0] * -1
        if abs(back_right_vector[1] - self.back_right.prev_angle) > 90 and abs(back_right_vector[1] - self.back_right.prev_angle) < 270:
            back_right_vector[1] = (back_right_vector[1] + 180) % 360
            # reverse speed of the module
            back_right_vector[0] = back_right_vector[0] * -1

        self.front_left.set_state(front_left_vector[0], front_left_vector[1])
        self.front_right.set_state(front_right_vector[0], front_right_vector[1])
        self.back_left.set_state(back_left_vector[0], back_left_vector[1])
        self.back_right.set_state(back_right_vector[0], back_right_vector[1])

        # Update the prev_angle of each module
        self.front_left.prev_angle = front_left_vector[1]
        self.front_right.prev_angle = front_right_vector[1]
        self.back_left.prev_angle = back_left_vector[1]
        self.back_right.prev_angle = back_right_vector[1]

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
        
    def absolute_encoders_callback(self, msg: AbsoluteEncoders) -> None:
        """This method is called whenever a message is received on the absoluteEncoders topic."""
        self.front_left.current_absolute_angle = (360 * msg.front_left_encoder / 1023) - self.FRONT_LEFT_MAGNET_OFFSET
        self.front_right.current_absolute_angle = (360 * msg.front_right_encoder / 1023) - self.FRONT_RIGHT_MAGNET_OFFSET
        self.back_left.current_absolute_angle = (360 * msg.back_left_encoder / 1023) - self.BACK_LEFT_MAGNET_OFFSET
        self.back_right.current_absolute_angle = (360 * msg.back_right_encoder / 1023) - self.BACK_RIGHT_MAGNET_OFFSET


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
