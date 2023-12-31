# This ROS 2 node contains code for the skimmer subsystem of the robot.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2023
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: November 2023

# Import the ROS 2 Python module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from std_msgs.msg import Float32, Bool

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import MotorCommandSet, MotorCommandGet
from rovr_interfaces.srv import SetPower, Stop, SetHeight


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
        self.srv_setHeight = self.create_service(SetHeight, "skimmer/setHeight", self.set_height_callback)
        self.srv_stop_height_adjust = self.create_service(Stop, "pulley/stop", self.stop_height_callback)
        self.srv_set_power_Pulley = self.create_service(SetPower, "pulley/setPower", self.set_power_pulley_callback)
        
        # Define publishers here
        self.publisher_height = self.create_publisher(Float32, "skimmer/height", 10)
        self.publisher_goal_reached = self.create_publisher(Bool, "skimmer/goal_reached", 10)

        # Define timers here
        self.timer = self.create_timer(0.1, self.timer_callback)
        
        # Define default values for our ROS parameters below #
        self.declare_parameter("SKIMMER_BELT_MOTOR", 9)
        self.declare_parameter("HEIGHT_ADJUST_MOTOR", 10)
        
        # Assign the ROS Parameters to member variables below #
        self.SKIMMER_BELT_MOTOR = self.get_parameter("SKIMMER_BELT_MOTOR").value
        self.HEIGHT_ADJUST_MOTOR = self.get_parameter("HEIGHT_ADJUST_MOTOR").value
        
        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("SKIMMER_BELT_MOTOR has been set to: " + str(self.SKIMMER_BELT_MOTOR))
        self.get_logger().info("HEIGHT_ADJUST_MOTOR has been set to: " + str(self.HEIGHT_ADJUST_MOTOR))

        # Current state of the skimmer belt
        self.running = False
        # Current goal height
        self.current_goal_height = 0  # relative encoders always initialize to 0
        # Goal Threshold (if abs(self.current_goal_height - ACTUAL VALUE) <= self.goal_threshold then we should publish True to /skimmer/goal_reached)
        self.goal_threshold = 0.1
        # Current state of the pulley system
        self.pulley_running = False
        # ----------------------------------------------------------------
        # Circumference of height adjust motor
        self.PULLEY_CIRCUMFERENCE = 0.1  # meters # TODO: Ask mechanical team for this value on the final robot
        # Gear ratio
        self.PULLEY_GEAR_RATIO = 1 / 1  # TODO: Ask mechanical team for this value on the final robot
        # motor rotate 360 degrees -> self.height_adjust_circumference / self.gear_ratio
        # ----------------------------------------------------------------

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

    def set_height(self, height: float) -> None:
        """This method sets the height (in meters) of the skimmer."""
        self.current_goal_height = height  # goal height should be in meters
        height_degrees = self.PULLEY_GEAR_RATIO * (height / self.PULLEY_CIRCUMFERENCE) * 360
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="position", can_id=self.HEIGHT_ADJUST_MOTOR, value=height_degrees)
        )

    def stop_height_adjust(self) -> None:
        """This method stops the pulley."""
        self.pulley_running = False
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.HEIGHT_ADJUST_MOTOR, value=0.0)
        )

    def set_power_Pulley(self, power: float) -> None:
        """This method sets power to the pulley."""
        self.pulley_running = True
        self.cli_motor_set.call_async(
            MotorCommandSet.Request(type="duty_cycle", can_id=self.HEIGHT_ADJUST_MOTOR, value=power)
        )

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

    def set_height_callback(self, request, response):
        """This service request sets the height of the skimmer."""
        self.set_height(request.height)
        response.success = 0  # indicates success
        return response

    def stop_height_callback(self, request, response):
        """This service request stops the pulley."""
        self.stop_height_adjust()
        response.success = 0  # indicates success
        return response

    def set_power_pulley_callback(self, request, response):
        """This service request sets power to the skimmer belt."""
        self.set_power_Pulley(request.power)
        response.success = 0  # indicates success
        return response

    # Define timer callback methods here
    def timer_callback(self):
        """Publishes the current height in meters and whether or not the goal height has been reached."""
        # This MotorCommandGet service call will return a future object, that will eventually contain the position in degrees
        future = self.cli_motor_get.call_async(MotorCommandGet.Request(type="position", can_id=self.HEIGHT_ADJUST_MOTOR))
        future.add_done_callback(self.done_callback)
        
    def done_callback(self, future):
        height_degrees = future.result().data
        height_meters = (height_degrees * self.PULLEY_CIRCUMFERENCE) / (360 * self.PULLEY_GEAR_RATIO)

        height_msg = Float32(data=height_meters)
        self.publisher_height.publish(height_msg)

        goal_reached_msg = Bool(data=abs(self.current_goal_height - height_meters) <= self.goal_threshold)
        self.publisher_goal_reached.publish(goal_reached_msg)


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
