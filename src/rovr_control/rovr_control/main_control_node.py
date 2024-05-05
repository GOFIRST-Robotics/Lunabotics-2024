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
from rovr_interfaces.srv import SetPower, SetHeight
from rovr_interfaces.srv import Stop, Drive, MotorCommandGet, ResetOdom

# Import Python Modules
import asyncio  # Allows the use of asynchronous methods!
import subprocess  # This is for the webcam stream subprocesses
import signal  # Allows us to kill subprocesses
import os  # Allows us to kill subprocesses
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
    quat = R.from_euler("z", yaw - 15, degrees=True).as_quat()  # TODO: Why does this need to be offset?
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
        self.declare_parameter("skimmer_belt_power", -0.2)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_lift_manual_power", 0.05)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("autonomous_field_type", "top")  # The type of field ("top", "bottom", "nasa")

        # Assign the ROS Parameters to member variables below #
        self.autonomous_driving_power = self.get_parameter("autonomous_driving_power").value
        self.max_drive_power = self.get_parameter("max_drive_power").value
        self.max_turn_power = self.get_parameter("max_turn_power").value
        self.skimmer_belt_power = self.get_parameter("skimmer_belt_power").value
        self.skimmer_lift_manual_power = self.get_parameter("skimmer_lift_manual_power").value
        self.autonomous_field_type = self.get_parameter("autonomous_field_type").value

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("autonomous_driving_power has been set to: " + str(self.autonomous_driving_power))
        self.get_logger().info("max_drive_power has been set to: " + str(self.max_drive_power))
        self.get_logger().info("max_turn_power has been set to: " + str(self.max_turn_power))
        self.get_logger().info("skimmer_belt_power has been set to: " + str(self.skimmer_belt_power))
        self.get_logger().info("skimmer_lift_manual_power has been set to: " + str(self.skimmer_lift_manual_power))
        self.get_logger().info("autonomous_field_type has been set to: " + str(self.autonomous_field_type))

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

        # Define timers here
        self.apriltag_timer = self.create_timer(0.1, self.start_calibration_callback)
        self.apriltag_timer.cancel()  # Cancel the timer initially

        # Define service clients here
        self.cli_skimmer_toggle = self.create_client(SetPower, "skimmer/toggle")
        self.cli_skimmer_stop = self.create_client(Stop, "skimmer/stop")
        self.cli_skimmer_setPower = self.create_client(SetPower, "skimmer/setPower")
        self.cli_skimmer_setHeight = self.create_client(SetHeight, "skimmer/setHeight")
        self.cli_drivetrain_stop = self.create_client(Stop, "drivetrain/stop")
        self.cli_drivetrain_drive = self.create_client(Drive, "drivetrain/drive")
        self.cli_motor_get = self.create_client(MotorCommandGet, "motor/get")
        self.cli_lift_stop = self.create_client(Stop, "lift/stop")
        self.cli_lift_set_power = self.create_client(SetPower, "lift/setPower")
        self.cli_set_apriltag_odometry = self.create_client(ResetOdom, "resetOdom")

        # Define publishers and subscribers here
        self.drive_power_publisher = self.create_publisher(Twist, "cmd_vel", 10)
        self.joy_subscription = self.create_subscription(Joy, "joy", self.joystick_callback, 10)
        self.skimmer_goal_subscription = self.create_subscription(
            Bool, "/skimmer/goal_reached", self.skimmer_goal_callback, 10
        )

        self.started_calibration = False
        self.field_calibrated = False
        self.nav2 = BasicNavigator()  # Instantiate the BasicNavigator class

    def optimal_dig_location(self) -> list:
        try:
            available_dig_spots = []
            while len(available_dig_spots) == 0:
                if self.DANGER_THRESHOLD > self.REAL_DANGER_THRESHOLD:
                    self.get_logger().warn("No safe digging spots are available!")
                    break
                for i in range(int(4.07 / 0.10)):
                    if self.nav2.lineCost(-8.14 + i * 0.10, -8.14 + i * 0.10, 2.57, 0, 0.1) <= self.DANGER_THRESHOLD:
                        available_dig_spots.append((-8.14 + i * 0.10, 2.57))
                        i += 1 / 0.10
                self.DANGER_THRESHOLD += 5
            return available_dig_spots
        except Exception as e:
            self.get_logger().error(f"Error: {e}")
            return available_dig_spots

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

    async def calibrate_field_coordinates(self) -> None:
        """This method rotates until we can see apriltag(s) and then sets the map -> odom tf."""
        if not self.field_calibrated:
            self.get_logger().info("Beginning search for apriltags")
            while not self.cli_drivetrain_drive.wait_for_service():  # Wait for the drivetrain services to be available
                self.get_logger().warn("Waiting for drivetrain services to become available...")
                await asyncio.sleep(0.1)
            await self.cli_drivetrain_drive.call_async(
                Drive.Request(forward_power=0.0, horizontal_power=0.0, turning_power=0.15)
            )
        while not self.field_calibrated:
            future = self.cli_set_apriltag_odometry.call_async(ResetOdom.Request())
            future.add_done_callback(self.future_odom_callback)
            await asyncio.sleep(0.05)  # Allows other async tasks to continue running (this is non-blocking)
        self.get_logger().info("Field Coordinates Calibrated!")
        await self.cli_drivetrain_stop.call_async(Stop.Request())
        self.nav2.spin(3.14)  # Turn around 180 degrees to face the rest of the field
        while not self.nav2.isTaskComplete():  # Wait for the dig location to be reached
            await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
        self.apriltag_timer.cancel()
        self.end_autonomous()  # Return to Teleop mode

    async def travel_automation(self) -> None:
        """This method is used to automate the travel of the robot to the excavation zone."""
        self.get_logger().info("Starting Travel Automation!")
        try:
            await self.calibrate_field_coordinates()  # Calibrate the field coordinates first
            self.nav2.goToPose(self.travel_automation_location)  # Navigate to the excavation zone
            while not self.nav2.isTaskComplete():  # Wait for the excavation zone to be reached
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            if self.nav2.getResult() == TaskResult.FAILED:
                self.get_logger().error("Failed to reach the excavation zone!")
                self.end_autonomous()  # Return to Teleop mode
                return
            self.get_logger().info("Travel Automation Complete!")
            if self.travel_automation_process is None:
                self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:
            self.get_logger().warn("Travel Automation Terminated!")
            self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_dig_procedure(self) -> None:
        """This method lays out the procedure for autonomously digging!"""
        self.get_logger().info("\nStarting Autonomous Digging Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await self.cli_skimmer_setHeight.call_async(
                SetHeight.Request(height=2000)
            )  # Lower the skimmer into the ground # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            # Drive forward while digging
            self.nav2.driveOnHeading(dist=0.15, speed=0.25)  # TODO: Adjust these parameters
            while not self.nav2.isTaskComplete():  # Wait for the end of the driveOnHeading task
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            await self.cli_drivetrain_stop.call_async(Stop.Request())
            await self.cli_skimmer_stop.call_async(Stop.Request())
            await self.cli_skimmer_setHeight.call_async(
                SetHeight.Request(height=1000)
            )  # Raise the skimmer back up a bit # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Autonomous Digging Procedure Complete!\n")
            if self.autonomous_cycle_process is None:
                self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().warn("Autonomous Digging Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_offload_procedure(self) -> None:
        """This method lays out the procedure for autonomously offloading!"""
        self.get_logger().info("\nStarting Autonomous Offload Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_skimmer_setHeight.call_async(
                SetHeight.Request(height=500)
            )  # Raise up the skimmer in preparation for dumping # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Commence Offloading!")
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await asyncio.sleep(10)  # TODO: Tune how long to offload for (or try using ros_check_load instead)
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
            self.nav2.goToPose(self.optimal_dig_location())  # Navigate to the dig location
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
        if msg.buttons[A_BUTTON] == 1 and buttons[A_BUTTON] == 0:
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

        # Check if the travel automation button is pressed
        if msg.buttons[Y_BUTTON] == 1 and buttons[Y_BUTTON] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Autonomous"]
                self.travel_automation_process = asyncio.ensure_future(
                    self.travel_automation()
                )  # Start the travel_automation process
            elif self.state == states["Autonomous"]:
                self.travel_automation_process.cancel()  # Terminate the travel_automation_process process
                self.travel_automation_process = None

        # Check if the autonomous digging button is pressed
        if msg.buttons[BACK_BUTTON] == 1 and buttons[BACK_BUTTON] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Autonomous"]
                self.autonomous_digging_process = asyncio.ensure_future(
                    self.Autonomous_Dig_procedure()
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
                    self.Autonomous_Offload_procedure()
                )  # Start the auto dig process
            elif self.state == states["Autonomous"]:
                self.autonomous_offload_process.cancel()  # Terminate the auto offload process
                self.autonomous_offload_process = None

        # Check if the autonomous cycle button is pressed
        if msg.buttons[RIGHT_BUMPER] == 1 and buttons[RIGHT_BUMPER] == 0:
            if self.state == states["Teleop"]:
                self.stop_all_subsystems()  # Stop all subsystems
                self.state = states["Autonomous"]

                self.autonomous_cycle_process = asyncio.ensure_future(
                    self.auto_cycle_procedure()
                )  # Start the autonomous cycle!
            elif self.state == states["Autonomous"]:
                self.autonomous_cycle_process.cancel()  # Terminate the autonomous cycle process
                self.autonomous_cycle_process = None

        # Check if the camera toggle button is pressed
        if msg.buttons[START_BUTTON] == 1 and buttons[START_BUTTON] == 0:
            self.camera_view_toggled = not self.camera_view_toggled
            if self.camera_view_toggled:  # Start streaming /dev/front_webcam on port 5000
                if self.back_camera is not None:
                    # Kill the self.back_camera process
                    os.killpg(os.getpgid(self.back_camera.pid), signal.SIGTERM)
                    self.back_camera = None
                self.front_camera = subprocess.Popen(
                    'gst-launch-1.0 v4l2src device=/dev/front_webcam ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw(memory:NVMM),format=NV12" ! nvv4l2av1enc bitrate=200000 ! "video/x-av1" ! udpsink host=10.133.232.197 port=5000',
                    shell=True,
                    preexec_fn=os.setsid,
                )
            else:  # Start streaming /dev/back_webcam on port 5000
                if self.front_camera is not None:
                    # Kill the self.front_camera process
                    os.killpg(os.getpgid(self.front_camera.pid), signal.SIGTERM)
                    self.front_camera = None
                self.back_camera = subprocess.Popen(
                    'gst-launch-1.0 v4l2src device=/dev/back_webcam ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw(memory:NVMM),format=NV12" ! nvv4l2av1enc bitrate=200000 ! "video/x-av1" ! udpsink host=10.133.232.197  port=5000',
                    shell=True,
                    preexec_fn=os.setsid,
                )

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
