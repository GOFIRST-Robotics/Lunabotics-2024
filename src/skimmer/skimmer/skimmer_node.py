# This ROS 2 node contains code for the skimmer subsystem of the robot.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: November 2023

# Import the ROS 2 Python module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from std_msgs.msg import Bool

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import MotorCommandSet, MotorCommandGet
from rovr_interfaces.srv import SetPower, Stop, SetPosition
from rovr_interfaces.msg import LimitSwitches


class SkimmerNode(Node):
    def __init__(self):
        """Initialize the ROS 2 skimmer node."""
        super().__init__("skimmer")

        # Define service clients here
        self.cli_motor_set = self.create_client(MotorCommandSet, "motor/set")
        self.cli_motor_get = self.create_client(MotorCommandGet, "motor/get")

        # Define services (methods callable from the outside) here
        self.srv_toggle = self.create_service(SetPower, "skimmer/toggle", self.toggle_callback)
        self.srv_stop = self.create_service(Stop, "skimmer/stop", self.stop_callback)
        self.srv_setPower = self.create_service(SetPower, "skimmer/setPower", self.set_power_callback)
        self.srv_setPosition = self.create_service(SetPosition, "lift/setPosition", self.set_position_callback)
        self.srv_lift_stop = self.create_service(Stop, "lift/stop", self.stop_lift_callback)
        self.srv_lift_set_power = self.create_service(SetPower, "lift/setPower", self.lift_set_power_callback)
        self.srv_zero_lift = self.create_service(Stop, "lift/zero", self.zero_lift_callback)

        # Define publishers here
        self.publisher_goal_reached = self.create_publisher(Bool, "skimmer/goal_reached", 10)

        # Define subscribers here
        self.limit_switch_sub = self.create_subscription(LimitSwitches, "limitSwitches", self.limit_switch_callback, 10)

        # Define timers here
        self.timer = self.create_timer(0.1, self.timer_callback)

        # Define default values for our ROS parameters below #
        self.declare_parameter("SKIMMER_BELT_MOTOR", 2)
        self.declare_parameter("SKIMMER_LIFT_MOTOR", 1)

        # Assign the ROS Parameters to member variables below #
        self.SKIMMER_BELT_MOTOR = self.get_parameter("SKIMMER_BELT_MOTOR").value
        self.SKIMMER_LIFT_MOTOR = self.get_parameter("SKIMMER_LIFT_MOTOR").value

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("SKIMMER_BELT_MOTOR has been set to: " + str(self.SKIMMER_BELT_MOTOR))
        self.get_logger().info("SKIMMER_LIFT_MOTOR has been set to: " + str(self.SKIMMER_LIFT_MOTOR))

        self.lift_encoder_offset = 0  # measured in degrees

        # Current state of the skimmer belt
        self.running = False
        # Current goal position (in degrees)
        self.current_goal_position = 0
        # Current position of the lift motor in degrees
        self.current_position_degrees = 0  # Relative encoders always initialize to 0
        # Goal Threshold (if abs(self.current_goal_position - ACTUAL VALUE) <= self.goal_threshold then we should publish True to /skimmer/goal_reached)
        self.goal_threshold = 10  # in degrees # TODO: Tune this threshold if needed
        # Current state of the lift system
        self.lift_running = False

        # Limit Switch States
        self.top_limit_pressed = False
        self.bottom_limit_pressed = False

        # Maximum value of the lift motor encoder (bottom of the lift system) IN DEGREES
        self.MAX_ENCODER_DEGREES = (
            -3600 * 360 / 42
        )  # Multiply the max encoder count (-3600) by 360 and divide by 42 to get degrees

    # Define subsystem methods here
    def set_power(self, skimmer_power: float) -> None:
        """This method sets power to the skimmer belt."""
        self.running = True
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.SKIMMER_BELT_MOTOR, value=skimmer_power)
        )

    def stop(self) -> None:
        """This method stops the skimmer belt."""
        self.running = False
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.SKIMMER_BELT_MOTOR, value=0.0)
        )

    def toggle(self, skimmer_belt_power: float) -> None:
        """This method toggles the skimmer belt."""
        if self.running:
            self.stop()
        else:
            self.set_power(skimmer_belt_power)

    def set_position(self, position: int) -> None:
        """This method sets the position (in degrees) of the skimmer."""
        self.current_goal_position = position  # goal position should be in degrees
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(
                type="position",
                can_id=self.SKIMMER_LIFT_MOTOR,
                value=float(self.current_goal_position + self.lift_encoder_offset),
            )
        )

    def stop_lift(self) -> None:
        """This method stops the lift."""
        self.lift_running = False
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.SKIMMER_LIFT_MOTOR, value=0.0)
        )

    def lift_set_power(self, power: float) -> None:
        """This method sets power to the lift system."""
        self.lift_running = True
        if power > 0 and self.top_limit_pressed:
            self.get_logger().warn("WARNING: Top limit switch pressed!")
            self.stop_lift()  # Stop the lift system
            return
        if power < 0 and self.bottom_limit_pressed:
            self.get_logger().warn("WARNING: Bottom limit switch pressed!")
            self.stop_lift()  # Stop the lift system
            return
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.SKIMMER_LIFT_MOTOR, value=power)
        )

    def zero_lift(self) -> None:
        """This method zeros the lift system by slowly raising it until the top limit switch is pressed."""
        self.lift_set_power(0.05)

    # Define service callback methods here
    def set_power_callback(self, request, response):
        """This service request sets power to the skimmer belt."""
        self.set_power(request.power)
        response.success = 0  # indicates success
        return response

    def stop_callback(self, request, response):
        """This service request stops the skimmer belt."""
        self.stop()
        response.success = 0  # indicates success
        return response

    def toggle_callback(self, request, response):
        """This service request toggles the skimmer belt."""
        self.toggle(request.power)
        response.success = 0  # indicates success
        return response

    def set_position_callback(self, request, response):
        """This service request sets the position of the lift."""
        self.set_position(request.position)
        response.success = 0  # indicates success
        return response

    def stop_lift_callback(self, request, response):
        """This service request stops the lift system."""
        self.stop_lift()
        response.success = 0  # indicates success
        return response

    def lift_set_power_callback(self, request, response):
        """This service request sets power to the skimmer belt."""
        self.lift_set_power(request.power)
        response.success = 0  # indicates success
        return response

    def zero_lift_callback(self, request, response):
        """This service request zeros the lift system."""
        self.zero_lift()
        response.success = 0  # indicates success
        return response

    # Define timer callback methods here
    def timer_callback(self):
        """Publishes whether or not the current goal position has been reached."""
        # This MotorCommandGet service call will return a future object, that will eventually contain the position in degrees
        future = self.cli_motor_get.call_async(MotorCommandGet.Request(type="position", can_id=self.SKIMMER_LIFT_MOTOR))
        future.add_done_callback(self.done_callback)

    def done_callback(self, future):
        self.current_position_degrees = future.result().data

        goal_reached_msg = Bool(
            data=abs(self.current_goal_position - self.current_position_degrees) <= self.goal_threshold
        )
        self.publisher_goal_reached.publish(goal_reached_msg)

    # Define subscriber callback methods here
    def limit_switch_callback(self, limit_switches_msg):
        """This subscriber callback method is called whenever a message is received on the limitSwitches topic."""
        if not self.top_limit_pressed and limit_switches_msg.top_limit_switch:
            self.stop_lift()  # Stop the lift system
        if not self.bottom_limit_pressed and limit_switches_msg.bottom_limit_switch:
            self.stop_lift()  # Stop the lift system
        self.top_limit_pressed = limit_switches_msg.top_limit_switch
        self.bottom_limit_pressed = limit_switches_msg.bottom_limit_switch
        if self.top_limit_pressed:  # If the top limit switch is pressed
            self.lift_encoder_offset = self.current_position_degrees
            self.get_logger().info("Current position in degrees: " + str(self.current_position_degrees))
            self.get_logger().info("New lift encoder offset: " + str(self.lift_encoder_offset))
        elif self.bottom_limit_pressed:  # If the bottom limit switch is pressed
            self.lift_encoder_offset = self.current_position_degrees - self.MAX_ENCODER_DEGREES
            self.get_logger().info("Current position in degrees: " + str(self.current_position_degrees))
            self.get_logger().info("New lift encoder offset: " + str(self.lift_encoder_offset))


def main(args=None):
    """The main function."""
    rclpy.init(args=args)

    node = SkimmerNode()
    node.get_logger().info("Initializing the Skimmer subsystem!")
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
