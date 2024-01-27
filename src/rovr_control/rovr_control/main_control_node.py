# This node contains the main control flow of our robot code.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2022
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: November 2023

# Import the ROS 2 module
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor  # This is needed to run multiple callbacks in a single thread

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist, Vector3, PoseWithCovarianceStamped
from sensor_msgs.msg import Joy
from tf2_msgs.msg import TFMessage
from std_msgs.msg import Bool

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import SetPower, SetHeight
from rovr_interfaces.srv import Stop, Drive, MotorCommandGet, ResetOdom

# Import Python Modules
import asyncio  # Allows the use of asynchronous methods!
import subprocess  # This is for the webcam stream subprocesses
import signal  # Allows us to kill subprocesses
import os  # Allows us to kill subprocesses

# Import our logitech gamepad button mappings
from .gamepad_constants import *

# Uncomment the line below to use the Xbox controller mappings instead
# from .xbox_controller_constants import *

# GLOBAL VARIABLES #
buttons = [0] * 11  # This is to help with button press detection
# Define the possible states of our robot
states = {"Teleop": 0, "Auto_Dig": 1, "Auto_Offload": 2}


class MainControlNode(Node):
    def __init__(self) -> None:
        """Initialize the ROS2 Node."""
        super().__init__("rovr_control")

        # Define default values for our ROS parameters below #
        self.declare_parameter("autonomous_driving_power", 0.25)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_drive_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_turn_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_belt_power", 0.35)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("skimmer_lift_manual_power", 0.35)  # Measured in Duty Cycle (0.0-1.0)

        # Assign the ROS Parameters to member variables below #
        self.autonomous_driving_power = self.get_parameter("autonomous_driving_power").value
        self.max_drive_power = self.get_parameter("max_drive_power").value
        self.max_turn_power = self.get_parameter("max_turn_power").value
        self.skimmer_belt_power = self.get_parameter("skimmer_belt_power").value
        self.skimmer_lift_manual_power = self.get_parameter("skimmer_lift_manual_power").value

        # Print the ROS Parameters to the terminal below #
        self.get_logger().info("autonomous_driving_power has been set to: " + str(self.autonomous_driving_power))
        self.get_logger().info("max_drive_power has been set to: " + str(self.max_drive_power))
        self.get_logger().info("max_turn_power has been set to: " + str(self.max_turn_power))
        self.get_logger().info("skimmer_belt_power has been set to: " + str(self.skimmer_belt_power))
        self.get_logger().info("skimmer_lift_manual_power has been set to: " + str(self.skimmer_lift_manual_power))

        # Define some initial states here
        self.state = states["Teleop"]
        self.camera_view_toggled = False
        self.front_camera = None
        self.back_camera = None
        self.autonomous_digging_process = None
        self.autonomous_offload_process = None
        self.skimmer_goal_reached = True

        # This is a hard-coded physical constant (how far off-center the apriltag camera is)
        self.apriltag_camera_offset = 0.1905  # Measured in Meters
        self.apriltag_timer = self.create_timer(.1, self.publish_odom_callback)

        # These variables store the most recent Apriltag pose
        self.apriltagX = 0.0
        self.apriltagZ = 0.0
        self.apriltagYaw = 0.0

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
        self.apriltag_pose_publisher = self.create_publisher(PoseWithCovarianceStamped, "apriltag_pose", 10)
        self.joy_subscription = self.create_subscription(Joy, "joy", self.joystick_callback, 10)
        self.apriltags_subscription = self.create_subscription(TFMessage, "tf", self.apriltags_callback, 10)
        self.skimmer_goal_subscription = self.create_subscription(Bool, "/skimmer/goal_reached", self.skimmer_goal_callback, 10)

    def publish_odom_callback(self) -> None:
        """This method publishes the odometry of the robot."""
        future = self.cli_set_apriltag_odometry.call_async(ResetOdom.Request())
        future.add_done_callback(self.future_odom_callback)

    def future_odom_callback(self, future) -> None:
        if future.result().success:
            self.get_logger().info("Apriltag Odometry Published")
            self.apriltag_timer.cancel()

    def stop_all_subsystems(self) -> None:
        """This method stops all subsystems on the robot."""
        self.cli_skimmer_stop.call_async(Stop.Request())  # Stop the skimmer belt
        self.cli_drivetrain_stop.call_async(Stop.Request())  # Stop the drivetrain
        self.cli_lift_stop.call_async(Stop.Request())  # Stop the skimmer lift

    def end_autonomous(self) -> None:
        """This method returns to teleop control."""
        self.stop_all_subsystems()  # Stop all subsystems
        self.state = states["Teleop"]  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_dig_procedure(self) -> None:
        """This method lays out the procedure for autonomously digging!"""
        self.get_logger().info("\nStarting Autonomous Digging Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await self.cli_skimmer_setHeight.call_async(SetHeight.Request(height=2000))  # Lower the skimmer into the ground # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            # Start driving forward
            await self.cli_drivetrain_drive.call_async(Drive.Request(forward_power=self.autonomous_driving_power, horizontal_power=0.0, turning_power=0.0))
            # TODO: Drive forward until our skimmer is full OR we reach the end of the arena OR we reach an obstacle
            await self.cli_drivetrain_stop.call_async(Stop.Request())
            await self.cli_skimmer_stop.call_async(Stop.Request())
            await self.cli_skimmer_setHeight.call_async(SetHeight.Request(height=1000))  # Raise the skimmer back up a bit # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Autonomous Digging Procedure Complete!\n")
            self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().info("Autonomous Digging Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    # TODO: This autonomous routine has not been tested yet!
    async def auto_offload_procedure(self) -> None:
        """This method lays out the procedure for autonomously offloading!"""
        self.get_logger().info("\nStarting Autonomous Offload Procedure!")
        try:  # Wrap the autonomous procedure in a try-except
            await self.cli_skimmer_setHeight.call_async(SetHeight.Request(height=500))  # Raise up the skimmer in preparation for dumping # TODO: Adjust this height
            # Wait for the goal height to be reached
            while not self.skimmer_goal_reached:
                await asyncio.sleep(0.1)  # Allows other async tasks to continue running (this is non-blocking)
            self.get_logger().info("Commence Offloading!")
            await self.cli_skimmer_setPower.call_async(SetPower.Request(power=self.skimmer_belt_power))
            await asyncio.sleep(10)  # How long to offload for
            await self.cli_skimmer_stop.call_async(Stop.Request())  # Stop the skimmer belt
            self.get_logger().info("Autonomous Offload Procedure Complete!\n")
            self.end_autonomous()  # Return to Teleop mode
        except asyncio.CancelledError:  # Put termination code here
            self.get_logger().info("Autonomous Offload Procedure Terminated\n")
            self.end_autonomous()  # Return to Teleop mode

    def apriltags_callback(self, msg: TFMessage) -> None:
        """Process the Apriltag detections."""
        array = msg.transforms
        entry = array.pop()

        # Create a PoseWithCovarianceStamped object from the Apriltag detection
        pose_object = PoseWithCovarianceStamped()
        pose_object.header = entry.header
        pose_object.pose.pose.position.x = entry.transform.translation.x + self.apriltag_camera_offset
        pose_object.pose.pose.position.y = entry.transform.translation.y
        pose_object.pose.pose.position.z = entry.transform.translation.z
        pose_object.pose.pose.orientation.x = entry.transform.rotation.x
        pose_object.pose.pose.orientation.y = entry.transform.rotation.y
        pose_object.pose.pose.orientation.z = entry.transform.rotation.z
        pose_object.pose.pose.orientation.w = entry.transform.rotation.w
        pose_object.pose.covariance = [0.0] * 36
        self.apriltag_pose_publisher.publish(pose_object)

        ## Set the value of these variables used for docking with an Apriltag ##

        # Left-Right Distance to the tag (measured in meters)
        self.apriltagX = entry.transform.translation.x + self.apriltag_camera_offset
        # Forward-Backward Distance to the tag (measured in meters)
        self.apriltagZ = entry.transform.translation.z
        # Yaw Angle error to the tag's orientation (measured in radians)
        self.apriltagYaw = entry.transform.rotation.y
        self.get_logger().debug('x: ' + str(self.apriltagX) + ' z:' + str(self.apriltagZ) + ' yaw: ' + str(self.apriltagYaw))

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
                Twist(linear=Vector3(x=horizontal_power, y=forward_power), angular=Vector3(z=turn_power))
            )

            # Check if the skimmer button is pressed #
            if msg.buttons[X_BUTTON] == 1 and buttons[X_BUTTON] == 0:
                self.cli_skimmer_toggle.call_async(SetPower.Request(power=self.skimmer_belt_power))

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
    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
