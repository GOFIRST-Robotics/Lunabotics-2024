# This node contains the main control flow of our robot code.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2022
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: November 2023

# Import the ROS 2 module
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor  # This is needed to run multiple callbacks in a single thread

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist, Vector3
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import SetPower, SetPosition
from rovr_interfaces.srv import Stop, Drive, MotorCommandGet, ResetOdom

# Import Python Modules
import asyncio  # Allows the use of asynchronous methods!

# Provides a “navigation as a library” capability
from nav2_simple_commander.robot_navigator import BasicNavigator

# Import our logitech gamepad button mappings
from .gamepad_constants import *

# Uncomment the line below to use the Xbox controller mappings instead
# from .xbox_controller_constants import *

# GLOBAL VARIABLES #
buttons = [0] * 11  # This is to help with button press detection
# Define the possible states of our robot
states = {"Teleop": 0, "Auto_Dig": 1, "Auto_Offload": 2, "Calibrating": 3}


class MainControlNode(Node):
    def __init__(self) -> None:
        """Initialize the ROS2 Node."""
        super().__init__("rovr_control")

        # Define default values for our ROS parameters below #
        self.declare_parameter("autonomous_driving_power", 0.25)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_drive_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_turn_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_belt_power", -0.3)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_lift_manual_power", 0.05)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("lift_dumping_position", -1000)  # Measured in encoder counts
        self.declare_parameter("lift_digging_position", -3200)  # Measured in encoder counts

        # Assign the ROS Parameters to member variables below #
        self.autonomous_driving_power = self.get_parameter("autonomous_driving_power").value
        self.max_drive_power = self.get_parameter("max_drive_power").value
        self.max_turn_power = self.get_parameter("max_turn_power").value
        self.skimmer_belt_power = self.get_parameter("skimmer_belt_power").value
        self.skimmer_lift_manual_power = self.get_parameter("skimmer_lift_manual_power").value
        self.lift_dumping_position = self.get_parameter("lift_dumping_position").value * 360 / 42  # Convert encoder counts to degrees
        self.lift_digging_position = self.get_parameter("lift_digging_position").value * 360 / 42  # Convert encoder counts to degrees

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("autonomous_driving_power has been set to: " + str(self.autonomous_driving_power))
        self.get_logger().info("max_drive_power has been set to: " + str(self.max_drive_power))
        self.get_logger().info("max_turn_power has been set to: " + str(self.max_turn_power))
        self.get_logger().info("skimmer_belt_power has been set to: " + str(self.skimmer_belt_power))
        self.get_logger().info("skimmer_lift_manual_power has been set to: " + str(self.skimmer_lift_manual_power))
        self.get_logger().info("lift_dumping_position has been set to: " + str(self.lift_dumping_position))
        self.get_logger().info("lift_digging_position has been set to: " + str(self.lift_digging_position))

        # Define some initial states here
        self.state = states["Teleop"]
        self.camera_view_toggled = False
        self.front_camera = None
        self.back_camera = None
        self.autonomous_digging_process = None
        self.autonomous_offload_process = None
        self.skimmer_goal_reached = True

        # Define timers here
        self.apriltag_timer = self.create_timer(0.1, self.start_calibration_callback)
        self.apriltag_timer.cancel()  # Cancel the apriltag timer initially

        # Define service clients here
        self.cli_skimmer_toggle = self.create_client(SetPower, "skimmer/toggle")
        self.cli_skimmer_stop = self.create_client(Stop, "skimmer/stop")
        self.cli_skimmer_setPower = self.create_client(SetPower, "skimmer/setPower")
        self.cli_lift_setPosition = self.create_client(SetPosition, "lift/setPosition")
        self.cli_drivetrain_stop = self.create_client(Stop, "drivetrain/stop")
        self.cli_drivetrain_drive = self.create_client(Drive, "drivetrain/drive")
        self.cli_motor_get = self.create_client(MotorCommandGet, "motor/get")
        self.cli_lift_stop = self.create_client(Stop, "lift/stop")
        self.cli_lift_zero = self.create_client(Stop, "lift/zero")
        self.cli_lift_set_power = self.create_client(SetPower, "lift/setPower")
        self.cli_set_apriltag_odometry = self.create_client(ResetOdom, "resetOdom")

        # Define publishers and subscribers here
        self.drive_power_publisher = self.create_publisher(Twist, "cmd_vel", 10)
        self.joy_subscription = self.create_subscription(Joy, "joy", self.joystick_callback, 10)
        self.skimmer_goal_subscription = self.create_subscription(Bool, "/skimmer/goal_reached", self.skimmer_goal_callback, 10)

        self.started_calibration = False
        self.field_calibrated = False
        self.nav2 = BasicNavigator()  # Instantiate the BasicNavigator class

        # ----- !! BLOCKING WHILE LOOP !! ----- #
        while not self.cli_lift_zero.wait_for_service(timeout_sec=1):
            self.get_logger().warn("Waiting for the lift/zero service to be available (BLOCKING)")
        self.cli_lift_zero.call_async(Stop.Request())  # Zero the lift by slowly raising it up

    def start_calibration_callback(self) -> None:
        """This method publishes the odometry of the robot."""
        if not self.started_calibration:
            asyncio.ensure_future(self.calibrate_field_coordinates())
            self.started_calibration = True

    def future_odom_callback(self, future) -> None:
        if future.result().success:
            self.field_calibrated = True
            self.get_logger().info("map -> odom TF published!")

    def stop_all_subsystems(self) -> None:
        """This method stops all subsystems on the robot."""
        self.cli_skimmer_stop.call_async(Stop.Request())  # Stop the skimmer belt
        self.cli_drivetrain_stop.call_async(Stop.Request())  # Stop the drivetrain
        self.cli_lift_stop.call_async(Stop.Request())  # Stop the skimmer lift

    def end_autonomous(self) -> None:
        """This method returns to teleop control."""
        self.stop_all_subsystems()  # Stop all subsystems
        self.state = states["Teleop"]  # Return to Teleop mode

    # This autonomous routine has been tested and works!
    async def calibrate_field_coordinates(self) -> None:
        """This method rotates until we can see apriltag(s) and then sets the map -> odom tf."""
        if not self.field_calibrated:
            self.get_logger().info("Beginning search for apriltags")
            while not self.cli_drivetrain_drive.wait_for_service():  # Wait for the drivetrain services to be available
                self.get_logger().warn("Waiting for drivetrain services to become available...")
                await asyncio.sleep(0.1)
            await self.cli_drivetrain_drive.call_async(Drive.Request(forward_power=0.0, horizontal_power=0.0, turning_power=0.3))
        while not self.field_calibrated:
            future = self.cli_set_apriltag_odometry.call_async(ResetOdom.Request())
            future.add_done_callback(self.future_odom_callback)
            await asyncio.sleep(0.05)  # Allows other async tasks to continue running (this is non-blocking)
        self.get_logger().info("Field Coordinates Calibrated!")
        await self.cli_drivetrain_stop.call_async(Stop.Request())
        self.nav2.spin(3.14)  # Turn around 180 degrees to face the rest of the field
        while not self.nav2.isTaskComplete():
            await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
        self.apriltag_timer.cancel()
        self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_dig_procedure(self) -> None:
        """This method lays out the procedure for autonomously digging!"""
        self.get_logger().info("\nStarting Autonomous Digging Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_digging_position))  # Lower the skimmer into the ground
            self.skimmer_goal_reached = False
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to the goal")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            # Drive forward while digging
            self.nav2.driveOnHeading(dist=0.75, speed=0.1)  # TODO: Tune these values
            while not self.nav2.isTaskComplete():  # Wait for the end of the driveOnHeading task
                self.get_logger().info("Auto Driving")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_drivetrain_stop.call_async(Stop.Request())
            await self.cli_skimmer_stop.call_async(Stop.Request())
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_dumping_position))  # Raise the skimmer back up
            self.skimmer_goal_reached = False
            # Wait for the lift goal to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to the goal")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Autonomous Digging Procedure Complete!\n")
            self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().warn("Autonomous Digging Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    # This autonomous routine has been tested and works!
    async def auto_offload_procedure(self) -> None:
        """This method lays out the procedure for autonomously offloading!"""
        self.get_logger().info("\nStarting Autonomous Offload Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_dumping_position))  # Raise up the skimmer in preparation for dumping
            self.skimmer_goal_reached = False
            # Wait for the lift goal to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to the goal")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Commence Offloading!")
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await asyncio.sleep(8 / abs(self.skimmer_belt_power))  # How long to offload for # TODO: Adjust this time factor as needed
            await self.cli_skimmer_stop.call_async(Stop.Request())  # Stop the skimmer belt
            self.get_logger().info("Autonomous Offload Procedure Complete!\n")
            self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().warn("Autonomous Offload Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    def skimmer_goal_callback(self, msg: Bool) -> None:
        """Update the member variable accordingly."""
        self.skimmer_goal_reached = msg.data

    def joystick_callback(self, msg: Joy) -> None:
        """This method is called whenever a joystick message is received."""

        # PUT TELEOP CONTROLS BELOW #

        if self.state == states["Teleop"]:
            # Drive the robot using joystick input during Teleop
            forward_power = msg.axes[RIGHT_JOYSTICK_VERTICAL_AXIS] * self.max_drive_power  # Forward power
            horizontal_power = msg.axes[RIGHT_JOYSTICK_HORIZONTAL_AXIS] * self.max_drive_power  # Horizontal power
            turn_power = msg.axes[LEFT_JOYSTICK_HORIZONTAL_AXIS] * self.max_turn_power  # Turning power
            self.drive_power_publisher.publish(
                Twist(linear=Vector3(x=forward_power, y=horizontal_power), angular=Vector3(z=turn_power))
            )

            # Check if the skimmer button is pressed #
            if msg.buttons[X_BUTTON] == 1 and buttons[X_BUTTON] == 0:
                self.cli_skimmer_toggle.call_async(SetPower.Request(power=self.skimmer_belt_power))

            # Check if the reverse skimmer button is pressed #
            if msg.buttons[Y_BUTTON] == 1 and buttons[Y_BUTTON] == 0:
                self.cli_skimmer_setPower.call_async(SetPower.Request(power=-self.skimmer_belt_power))

            # Check if the lift dumping position button is pressed #
            if msg.buttons[B_BUTTON] == 1 and buttons[B_BUTTON] == 0:
                self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_dumping_position))

            # Check if the lift digging position button is pressed #
            if msg.buttons[A_BUTTON] == 1 and buttons[A_BUTTON] == 0:
                self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_digging_position))

            # Manually adjust the height of the skimmer with the left and right triggers
            if msg.buttons[RIGHT_TRIGGER] == 1 and buttons[RIGHT_TRIGGER] == 0:
                self.cli_lift_set_power.call_async(SetPower.Request(power=self.skimmer_lift_manual_power))
            elif msg.buttons[RIGHT_TRIGGER] == 0 and buttons[RIGHT_TRIGGER] == 1:
                self.cli_lift_stop.call_async(Stop.Request())
            elif msg.buttons[LEFT_TRIGGER] == 1 and buttons[LEFT_TRIGGER] == 0:
                self.cli_lift_set_power.call_async(SetPower.Request(power=-self.skimmer_lift_manual_power))
            elif msg.buttons[LEFT_TRIGGER] == 0 and buttons[LEFT_TRIGGER] == 1:
                self.cli_lift_stop.call_async(Stop.Request())

        # THE CONTROLS BELOW ALWAYS WORK #

        # Check if the Apriltag calibration button is pressed
        if msg.buttons[START_BUTTON] == 1 and buttons[START_BUTTON] == 0:
            # Start the field calibration process
            if self.apriltag_timer.is_canceled():
                self.started_calibration = False
                self.field_calibrated = False
                self.state = states["Calibrating"]  # Exit Teleop mode
                self.apriltag_timer.reset()
            # Stop the field calibration process
            else:
                self.apriltag_timer.cancel()
                self.get_logger().warn("Field Calibration Terminated\n")
                self.end_autonomous()  # Return to Teleop mode

        # Check if the autonomous digging button is pressed
        if msg.buttons[BACK_BUTTON] == 1 and buttons[BACK_BUTTON] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Auto_Dig"]
                self.autonomous_digging_process = asyncio.ensure_future(
                    self.auto_dig_procedure()
                )  # Start the auto dig process
            elif self.state == states["Auto_Dig"]:
                self.autonomous_digging_process.cancel()  # Terminate the auto dig process

        # Check if the autonomous offload button is pressed
        if msg.buttons[LEFT_BUMPER] == 1 and buttons[LEFT_BUMPER] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Auto_Offload"]
                self.autonomous_offload_process = asyncio.ensure_future(
                    self.auto_offload_procedure()
                )  # Start the auto dig process
            elif self.state == states["Auto_Offload"]:
                self.autonomous_offload_process.cancel()  # Terminate the auto offload process

        # Update button states (this allows us to detect changing button states)
        for index in range(len(buttons)):
            buttons[index] = msg.buttons[index]


async def spin(executor: SingleThreadedExecutor) -> None:
    """This function is called in the main function to run the executor."""
    while rclpy.ok():  # While ROS is still running
        executor.spin_once()  # Spin the executor once
        await asyncio.sleep(0)  # Setting the delay to 0 provides an optimized path to allow other tasks to run.


def main(args=None) -> None:
    rclpy.init(args=args)

    node = MainControlNode()  # Instantiate the node
    executor = SingleThreadedExecutor()  # Create an executor
    executor.add_node(node)  # Add the node to the executor

    node.get_logger().info("Hello from the rovr_control package!")

    loop = asyncio.get_event_loop()  # Get the event loop
    loop.run_until_complete(spin(executor))  # Run the spin function in the event loop

    # Clean up and shutdown
    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
