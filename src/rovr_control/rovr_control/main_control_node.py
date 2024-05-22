# This node contains the main control flow of our robot code.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2022
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: November 2023


# Import the ROS 2 module
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor  # This is needed to run multiple callbacks in a single thread

# Provides a “navigation as a library” capability
from nav2_simple_commander.robot_navigator import (
    BasicNavigator,
    TaskResult,
)

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist, Vector3, PoseStamped
from sensor_msgs.msg import Joy
from std_msgs.msg import Bool

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import SetPower, SetPosition
from rovr_interfaces.srv import Stop, Drive, MotorCommandGet, ResetOdom

# Import Python Modules
import math
import asyncio  # Allows the use of asynchronous methods!
from scipy.spatial.transform import Rotation as R

# Import our logitech gamepad button mappings
from .gamepad_constants import *

# Uncomment the line below to use the Xbox controller mappings instead
# from .xbox_controller_constants import *


# GLOBAL VARIABLES #
buttons = [0] * 11  # This is to help with button press detection
# Define the possible states of our robot
states = {"Teleop": 0, "Autonomous": 1}


# Helper Method
def create_pose_stamped(x, y, yaw):
    pose_stamped_msg = PoseStamped()
    pose_stamped_msg.header.frame_id = "map"
    pose_stamped_msg.pose.position.x = x
    pose_stamped_msg.pose.position.y = y
    quat = R.from_euler("z", yaw, degrees=True).as_quat()
    pose_stamped_msg.pose.orientation.x = quat[0]
    pose_stamped_msg.pose.orientation.y = quat[1]
    pose_stamped_msg.pose.orientation.z = quat[2]
    pose_stamped_msg.pose.orientation.w = quat[3]
    return pose_stamped_msg


class MainControlNode(Node):
    def __init__(self) -> None:
        """Initialize the ROS2 Node."""
        super().__init__("rovr_control")

        # Define default values for our ROS parameters below #
        self.declare_parameter("autonomous_driving_power", 0.25)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_drive_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_turn_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_belt_power", -0.3)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("autonomous_field_type", "bottom")  # The type of field ("top", "bottom", "nasa")
        self.declare_parameter("skimmer_lift_manual_power", 0.075)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("lift_dumping_position", -1000)  # Measured in encoder counts
        self.declare_parameter("lift_digging_start_position", -3050)  # Measured in encoder counts
        self.declare_parameter("lift_digging_end_position", -3150)  # Measured in encoder counts

        # Assign the ROS Parameters to member variables below #
        self.autonomous_driving_power = self.get_parameter("autonomous_driving_power").value
        self.max_drive_power = self.get_parameter("max_drive_power").value
        self.max_turn_power = self.get_parameter("max_turn_power").value
        self.skimmer_belt_power = self.get_parameter("skimmer_belt_power").value
        self.skimmer_lift_manual_power = self.get_parameter("skimmer_lift_manual_power").value
        self.autonomous_field_type = self.get_parameter("autonomous_field_type").value
        self.lift_dumping_position = self.get_parameter("lift_dumping_position").value * 360 / 42  # Convert encoder counts to degrees
        self.lift_digging_start_position = self.get_parameter("lift_digging_start_position").value * 360 / 42  # Convert encoder counts to degrees
        self.lift_digging_end_position = self.get_parameter("lift_digging_end_position").value * 360 / 42  # Convert encoder counts to degrees

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("autonomous_driving_power has been set to: " + str(self.autonomous_driving_power))
        self.get_logger().info("max_drive_power has been set to: " + str(self.max_drive_power))
        self.get_logger().info("max_turn_power has been set to: " + str(self.max_turn_power))
        self.get_logger().info("skimmer_belt_power has been set to: " + str(self.skimmer_belt_power))
        self.get_logger().info("skimmer_lift_manual_power has been set to: " + str(self.skimmer_lift_manual_power))
        self.get_logger().info("autonomous_field_type has been set to: " + str(self.autonomous_field_type))
        self.get_logger().info("lift_dumping_position has been set to: " + str(self.lift_dumping_position))
        self.get_logger().info("lift_digging_start_position has been set to: " + str(self.lift_digging_start_position))
        self.get_logger().info("lift_digging_end_position has been set to: " + str(self.lift_digging_end_position))

        # Define some initial states here
        self.state = states["Teleop"]
        self.camera_view_toggled = False
        self.front_camera = None
        self.back_camera = None
        self.autonomous_digging_process = None
        self.autonomous_offload_process = None
        self.autonomous_cycle_process = None
        self.travel_automation_process = None
        self.skimmer_goal_reached = True
        
        self.joystick_lagging_vertical = 0
        self.joystick_lagging_horizontal = 0
        self.joystick_lagging_turn = 0
        self.last_joystick_callback = self.get_clock().now().nanoseconds

        self.DANGER_THRESHOLD = 1
        self.REAL_DANGER_THRESHOLD = 100

        # Define important map locations
        if self.autonomous_field_type == "top":
            self.autonomous_berm_location = create_pose_stamped(7.25, -3.2, 90)  # TODO: Test this location in simulation
            self.travel_automation_location = create_pose_stamped(6.2, -1.2, 0)
        elif self.autonomous_field_type == "bottom":
            self.autonomous_berm_location = create_pose_stamped(7.25, -1.4, 270)
            self.travel_automation_location = create_pose_stamped(6.2, -3.2, 0)
        elif self.autonomous_field_type == "nasa":
            self.autonomous_berm_location = create_pose_stamped(1.3, -0.6, 90)  # TODO: Test this location in simulation
            self.travel_automation_location = create_pose_stamped(6.2, -1.2, 0)  # TODO: Test this location in simulation

        self.DANGER_THRESHOLD = 1
        self.REAL_DANGER_THRESHOLD = 100

        # Define important map locations
        if self.autonomous_field_type == "top":
            self.autonomous_berm_location = create_pose_stamped(7.25, -3.2, 90)  # TODO: Test this location in simulation
            self.travel_automation_location = create_pose_stamped(6.2, -1.2, 0)
        elif self.autonomous_field_type == "bottom":
            self.autonomous_berm_location = create_pose_stamped(7.25, -1.4, 270)
            self.travel_automation_location = create_pose_stamped(6.2, -3.2, 270)
        elif self.autonomous_field_type == "nasa":
            self.autonomous_berm_location = create_pose_stamped(1.3, -0.6, 90)  # TODO: Test this location in simulation
            self.travel_automation_location = create_pose_stamped(6.2, -1.2, 0)  # TODO: Test this location in simulation

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
        self.cli_drivetrain_calibrate = self.create_client(Stop, "drivetrain/calibrate")
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

    # def optimal_dig_location(self) -> list:
    #     available_dig_spots = []
    #     try:
    #         costmap = PyCostmap2D(self.nav2.getGlobalCostmap())
    #         resolution = costmap.getResolution()
    #         print(resolution)
    #         # NEEDED MEASUREMENTS:
    #         robot_width = 1.749 / 2
    #         robot_width_pixels = robot_width // resolution
    #         danger_threshold, real_danger_threshold = 50, 150
    #         dig_zone_depth, dig_zone_start, dig_zone_end = 2.57, 4.07, 8.14
    #         dig_zone_border_y = 2.0
    #         while len(available_dig_spots) == 0:
    #             if danger_threshold > real_danger_threshold:
    #                 self.get_logger().warn("No safe digging spots available. Switch to manual control.")
    #                 return None
    #             i = dig_zone_start + robot_width
    #             while i <= dig_zone_end - robot_width:
    #                 if costmap.getDigCost(i, dig_zone_border_y, robot_width_pixels, dig_zone_depth) <= self.DANGER_THRESHOLD:
    #                     available_dig_spots.append(create_pose_stamped(i, -dig_zone_border_y, 270))
    #                     i += robot_width
    #                 else:
    #                     i += resolution
    #             if len(available_dig_spots) > 0:
    #                 return available_dig_spots
    #             danger_threshold += 5
    #     except Exception as e:
    #         self.get_logger().error(f"Error in optimal_dig_location: {e} on line {sys.exc_info()[-1].tb_lineno}")
    #         return None

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

    # async def travel_automation(self) -> None:
    #     """This method is used to automate the travel of the robot to the excavation zone."""
    #     self.get_logger().info("Starting Travel Automation!")
    #     try:
    #         await self.calibrate_field_coordinates()  # Calibrate the field coordinates first
    #         self.nav2.goToPose(self.travel_automation_location)  # Navigate to the excavation zone
    #         while not self.nav2.isTaskComplete():  # Wait for the excavation zone to be reached
    #             await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
    #         if self.nav2.getResult() == TaskResult.FAILED:
    #             self.get_logger().error("Failed to reach the excavation zone!")
    #             self.end_autonomous()  # Return to Teleop mode
    #             return
    #         self.get_logger().info("Travel Automation Complete!")
    #         if self.travel_automation_process is None:
    #             self.end_autonomous()  # Return to Teleop mode
    #     except asyncio.CancelledError:
    #         self.get_logger().warn("Travel Automation Terminated!")
    #         self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_dig_procedure(self) -> None:
        """This method lays out the procedure for autonomously digging!"""
        self.get_logger().info("\nStarting Autonomous Digging Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_lift_zero.call_async(Stop.Request())
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_digging_start_position))  # Lower the skimmer onto the ground
            self.skimmer_goal_reached = False
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to starting dig position")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            # Drive forward while digging
            start_time = self.get_clock().now().nanoseconds
            elapsed = self.get_clock().now().nanoseconds - start_time
            # accelerate for 2 seconds
            while elapsed < 2e9:
                await self.cli_lift_set_power.call_async(SetPower.Request(power=-0.05e-9 * (elapsed)))
                await self.cli_drivetrain_drive.call_async(Drive.Request(forward_power=0.0, horizontal_power=0.25e-9 * (elapsed), turning_power=0.0))
                self.get_logger().info("Accelerating lift and drive train")
                elapsed = self.get_clock().now().nanoseconds - start_time
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            # keep digging at full speed for the remaining 10 seconds
            while self.get_clock().now().nanoseconds - start_time < 12e9:
                self.get_logger().info("Auto Driving")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_drivetrain_stop.call_async(Stop.Request())
            await self.cli_skimmer_stop.call_async(Stop.Request())
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_dumping_position))  # Raise the skimmer back up
            self.skimmer_goal_reached = False
            # Wait for the lift goal to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to dumping position")
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
            # Drive backward into the berm zone
            await self.cli_drivetrain_drive.call_async(Drive.Request(forward_power=0.0, horizontal_power=-0.25, turning_power=0.0))
            start_time = self.get_clock().now().nanoseconds
            while self.get_clock().now().nanoseconds - start_time < 10e9:
                self.get_logger().info("Auto Driving")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_drivetrain_stop.call_async(Stop.Request())
            # Raise up the skimmer in preparation for dumping
            await self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_dumping_position))
            self.skimmer_goal_reached = False
            # Wait for the lift goal to be reached
            while not self.skimmer_goal_reached:
                self.get_logger().info("Moving skimmer to the goal")
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Commence Offloading!")
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await asyncio.sleep(8 / abs(self.skimmer_belt_power))  # How long to offload for
            await self.cli_skimmer_stop.call_async(Stop.Request())  # Stop the skimmer belt
            self.get_logger().info("Autonomous Offload Procedure Complete!\n")
            if self.autonomous_cycle_process is None:
                self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().warn("Autonomous Offload Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_cycle_procedure(self) -> None:
        """This method lays out the procedure for doing a complete autonomous cycle!"""
        self.get_logger().info("\nStarting an Autonomous Cycle!")
        try:  # Wrap the autonomous procedure in a try-except
            ## Navigate to the dig_location, run the dig procedure, then navigate to the berm zone and run the offload procedure ##
            if not self.field_calibrated:
                self.get_logger().error("Field coordinates must be calibrated first!")
                self.end_autonomous()  # Return to Teleop mode
                return
            self.nav2.goToPose(self.travel_automation_location)  # Navigate to the dig location
            while not self.nav2.isTaskComplete():  # Wait for the dig location to be reached
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            if self.nav2.getResult() == TaskResult.FAILED:
                self.get_logger().error("Failed to reach the dig location!")
                self.end_autonomous()  # Return to Teleop mode
                return
            self.autonomous_digging_process = asyncio.ensure_future(
                self.auto_dig_procedure()
            )  # Start the auto dig process
            while not self.autonomous_digging_process.done():  # Wait for the dig process to complete
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.nav2.goToPose(self.autonomous_berm_location)  # Navigate to the berm zone
            while not self.nav2.isTaskComplete():  # Wait for the berm zone to be reached
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            if self.nav2.getResult() == TaskResult.FAILED:
                self.get_logger().error("Failed to reach the berm zone!")
                self.end_autonomous()  # Return to Teleop mode
                return
            self.autonomous_offload_process = asyncio.ensure_future(
                self.auto_offload_procedure()
            )  # Start the auto offload process
            while not self.autonomous_offload_process.done():  # Wait for the offload process to complete
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Completed an Autonomous Cycle!\n")
            self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().info("Autonomous Cycle Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    def skimmer_goal_callback(self, msg: Bool) -> None:
        """Update the member variable accordingly."""
        self.skimmer_goal_reached = msg.data

    def joystick_callback(self, msg: Joy) -> None:
        """This method is called whenever a joystick message is received."""

        # PUT TELEOP CONTROLS BELOW #

        if self.state == states["Teleop"]:
            # Drive the robot using joystick input during Teleop
            
            # Decrease Acceleration
            joystick_acceleration_constant = 0.1
            joystick_threshold = 0.1
            
            joystick_acceleration = (self.get_clock().now().nanoseconds - self.last_joystick_callback) / 1e9 * joystick_acceleration_constant
            joystick_vertical_movement = msg.axes[RIGHT_JOYSTICK_VERTICAL_AXIS] - self.joystick_lagging_vertical
            joystick_horizontal_movement = msg.axes[RIGHT_JOYSTICK_HORIZONTAL_AXIS] - self.joystick_lagging_horizontal
            joystick_turn_movement = msg.axes[LEFT_JOYSTICK_HORIZONTAL_AXIS] - self.joystick_lagging_turn
            
            self.joystick_lagging_vertical += 0 if abs(joystick_vertical_movement) < joystick_threshold else math.copysign(min(joystick_acceleration, abs(joystick_vertical_movement)), joystick_vertical_movement)
            self.joystick_lagging_horizontal += 0 if abs(joystick_horizontal_movement) < joystick_threshold else math.copysign(min(joystick_acceleration, abs(joystick_horizontal_movement), joystick_horizontal_movement))
            self.joystick_lagging_turn += 0 if abs(joystick_turn_movement) < joystick_threshold else math.copysign(min(joystick_acceleration, abs(joystick_turn_movement)), joystick_turn_movement)
            self.last_joystick_callback = self.get_clock().now().nanoseconds
            
            
            forward_power = self.joystick_lagging_vertical * self.max_drive_power  # Forward power
            horizontal_power = self.joystick_lagging_horizontal * self.max_drive_power  # Horizontal power
            turn_power = self.joystick_lagging_turn * self.max_turn_power  # Turning power
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
                self.cli_lift_setPosition.call_async(SetPosition.Request(position=self.lift_digging_start_position))

            # Manually adjust the height of the skimmer with the left and right triggers
            if msg.buttons[RIGHT_TRIGGER] == 1 and buttons[RIGHT_TRIGGER] == 0:
                self.cli_lift_set_power.call_async(SetPower.Request(power=self.skimmer_lift_manual_power))
            elif msg.buttons[RIGHT_TRIGGER] == 0 and buttons[RIGHT_TRIGGER] == 1:
                self.cli_lift_stop.call_async(Stop.Request())
            elif msg.buttons[LEFT_TRIGGER] == 1 and buttons[LEFT_TRIGGER] == 0:
                self.cli_lift_set_power.call_async(SetPower.Request(power=-self.skimmer_lift_manual_power))
            elif msg.buttons[LEFT_TRIGGER] == 0 and buttons[LEFT_TRIGGER] == 1:
                self.cli_lift_stop.call_async(Stop.Request())

            # Check if the calibration button is pressed
            if msg.buttons[RIGHT_BUMPER] == 1 and buttons[RIGHT_BUMPER] == 0:
                self.cli_drivetrain_calibrate.call_async(Stop.Request())

        # THE CONTROLS BELOW ALWAYS WORK #

        # Check if the Apriltag calibration button is pressed
        if msg.buttons[START_BUTTON] == 1 and buttons[START_BUTTON] == 0:
            # Start the field calibration process
            if self.apriltag_timer.is_canceled():
                self.started_calibration = False
                self.field_calibrated = False
                self.state = states["Autonomous"]  # Exit Teleop mode
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
                self.state = states["Autonomous"]
                self.autonomous_digging_process = asyncio.ensure_future(
                    self.auto_dig_procedure()
                )  # Start the auto dig process
            elif self.state == states["Autonomous"]:
                self.autonomous_digging_process.cancel()  # Terminate the auto dig process
                self.autonomous_digging_process = None

        # Check if the autonomous offload button is pressed
        if msg.buttons[LEFT_BUMPER] == 1 and buttons[LEFT_BUMPER] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Autonomous"]
                self.autonomous_offload_process = asyncio.ensure_future(
                    self.auto_offload_procedure()
                )  # Start the auto dig process
            elif self.state == states["Autonomous"]:
                self.autonomous_offload_process.cancel()  # Terminate the auto offload process
                self.autonomous_offload_process = None

        # # Check if the autonomous cycle button is pressed
        # if msg.buttons[RIGHT_BUMPER] == 1 and buttons[RIGHT_BUMPER] == 0:
        #     if self.state == states["Teleop"]:
        #         self.stop_all_subsystems()  # Stop all subsystems
        #         self.state = states["Autonomous"]
        #         self.autonomous_cycle_process = asyncio.ensure_future(
        #             self.auto_cycle_procedure()
        #         )  # Start the autonomous cycle!
        #     elif self.state == states["Autonomous"]:
        #         self.autonomous_cycle_process.cancel()  # Terminate the autonomous cycle process
        #         self.autonomous_cycle_process = None

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
    node.nav2.lifecycleShutdown()
    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
