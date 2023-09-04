# This node contains the main control flow of our robot code.
# Original Author: Anthony Brogni <brogn002@umn.edu> in Fall 2022
# Maintainer: Anthony Brogni <brogn002@umn.edu>
# Last Updated: September 2023

# Import the ROS 2 module
import rclpy
from rclpy.node import Node

# Import ROS 2 formatted message types
from geometry_msgs.msg import Twist, Vector3, PoseWithCovarianceStamped
from sensor_msgs.msg import Joy
from tf2_msgs.msg import TFMessage

# Import custom ROS 2 interfaces
from rovr_interfaces.srv import OffloaderToggle, OffloaderSetPower
from rovr_interfaces.srv import ConveyorToggle, ConveyorSetPower
from rovr_interfaces.srv import DiggerToggle, DiggerSetPower
from rovr_interfaces.srv import Stop, Drive, MotorCommandGet

# Import Python Modules
import multiprocessing  # Allows us to run tasks in parallel using multiple CPU cores!
import subprocess  # This is for the webcam stream subprocesses
import signal  # Allows us to kill subprocesses
import serial  # Serial communication with the Arduino. Install with: <sudo pip3 install pyserial>
import time  # This is for time.sleep()
import os  # Allows us to kill subprocesses
import re  # Enables using regular expressions

# Import our gamepad button mappings
from .gamepad_constants import *

# GLOBAL VARIABLES #
buttons = [0] * 11  # This is to help with button press detection
# Define the possible states of our robot
states = {
    "Teleop": 0,
    "Auto_Dig": 1
}

def get_target_ip(target: str, default: str = "", logger_fn=print):
    """Return the current IP address of the laptop using nmap."""
    try:
        nmap = subprocess.Popen(
            ("nmap", "-sn", "192.168.1.1/24"), stdout=subprocess.PIPE
        )
        grep = subprocess.check_output(("grep", target), stdin=nmap.stdout)
        nmap.wait()
        res = re.sub(r".*\((.*)\).*", r"\g<1>", grep.decode())
        if not res:
            raise Exception("target not found")
        return res
    except:
        logger_fn(f"target not found; defaulting to {default}")
        return default


class MainControlNode(Node):
    def __init__(self):
        """Initialize the ROS2 Node."""
        super().__init__("rovr_control")
        
        # Define default values for our ROS parameters below #
        self.declare_parameter("autonomous_driving_power", 0.25)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_drive_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("max_turn_power", 1.0)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("linear_actuator_speed", 8)  # Duty Cycle value between 0-100 (not 0.0-1.0)
        self.declare_parameter("linear_actuator_up_speed", 40)  # Duty Cycle value between 0-100 (not 0.0-1.0)
        self.declare_parameter("small_linear_actuator_speed", 75)  # Duty Cycle value between 0-100 (not 0.0-1.0)
        self.declare_parameter("digger_rotation_power", 0.4)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("drum_belt_power", 0.2)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("conveyor_belt_power", 0.35)  # Measured in Duty Cycle (0.0-1.0)
        self.declare_parameter("offload_belt_power", 0.35)  # Measured in Duty Cycle (0.0-1.0)
        
        # Assign the ROS Parameters
        self.autonomous_driving_power = self.get_parameter("autonomous_driving_power").value
        self.max_drive_power = self.get_parameter("max_drive_power").value
        self.max_turn_power = self.get_parameter("max_turn_power").value
        self.digger_rotation_power = self.get_parameter("digger_rotation_power").value
        self.drum_belt_power = self.get_parameter("drum_belt_power").value
        self.conveyor_belt_power = self.get_parameter("conveyor_belt_power").value
        self.offload_belt_power = self.get_parameter("offload_belt_power").value
        self.linear_actuator_speed = self.get_parameter("linear_actuator_speed").value
        self.linear_actuator_up_speed = self.get_parameter("linear_actuator_up_speed").value
        self.small_linear_actuator_speed = self.get_parameter("small_linear_actuator_speed").value
        
        # Print the ROS Parameters to the terminal
        print("autonomous_driving_power has been set to:", self.autonomous_driving_power)
        print("max_drive_power has been set to:", self.max_drive_power)
        print("max_turn_power has been set to:", self.max_turn_power)
        print("linear_actuator_speed has been set to:", self.linear_actuator_speed)
        print("linear_actuator_up_speed has been set to:", self.linear_actuator_up_speed)
        print("small_linear_actuator_speed has been set to:", self.small_linear_actuator_speed)
        print("digger_rotation_power has been set to:", self.digger_rotation_power)
        print("drum_belt_power has been set to:", self.drum_belt_power)
        print("conveyor_belt_power has been set to:", self.conveyor_belt_power)
        print("offload_belt_power has been set to:", self.offload_belt_power)

        # NOTE: The code commented out below is for dynamic ip address asignment, but we haven't gotten it to work yet
        # self.target_ip = get_target_ip('blixt-G14', '192.168.1.110', self.get_logger().info)
        # self.get_logger().info(f'set camera stream target ip to {self.target_ip}')

        # Try connecting to the Arduino over Serial
        try:
            # Set this as a static Serial port!
            self.arduino = serial.Serial("/dev/Arduino_Uno", 9600)
        except Exception as e:
            print(e)  # If an exception is raised, print it, and then move on

        # Define some initial states here
        self.state = states["Teleop"] 
        self.digger_extend_toggled = False
        self.camera_view_toggled = False
        self.front_camera = None
        self.back_camera = None
        self.autonomous_digging_process = None

        # This is a hard-coded physical constant (how far off-center the apriltag camera is)
        self.typeapriltag_camera_offset = 0.1905  # Measured in Meters
        
        # These variables store the most recent Apriltag pose
        self.apriltagX = 0.0
        self.apriltagZ = 0.0
        self.apriltagYaw = 0.0
        
        # Define service clients here
        self.cli_offloader_toggle = self.create_client(OffloaderToggle, "offloader/toggle")
        self.cli_offloader_stop = self.create_client(Stop, "offloader/stop")
        self.cli_offloader_setPower = self.create_client(OffloaderSetPower, "offloader/setPower")
        self.cli_conveyor_toggle = self.create_client(ConveyorToggle, "conveyor/toggle")
        self.cli_conveyor_stop = self.create_client(Stop, "conveyor/stop")
        self.cli_conveyor_setPower = self.create_client(ConveyorSetPower, "conveyor/setPower")
        self.cli_digger_toggle = self.create_client(DiggerToggle, "digger/toggle")
        self.cli_digger_stop = self.create_client(Stop, "digger/stop")
        self.cli_digger_setPower = self.create_client(DiggerSetPower, "digger/setPower")
        self.cli_drivetrain_stop = self.create_client(Stop, "drivetrain/stop")
        self.cli_drivetrain_drive = self.create_client(Drive, "drivetrain/drive")
        self.cli_motor_get = self.create_client(MotorCommandGet, "motor/get")

        # Define publishers and subscribers here
        self.drive_power_publisher = self.create_publisher(Twist, "cmd_vel", 10)
        self.apriltag_pose_publisher = self.create_publisher(PoseWithCovarianceStamped, "apriltag_pose", 10)
        self.joy_subscription = self.create_subscription(Joy, "joy", self.joystick_callback, 10)
        self.apriltags_subscription = self.create_subscription(TFMessage, "tf", self.apriltags_callback, 10)

    def auto_dig_procedure(self):
        """This method lays out the procedure for autonomously digging!"""
        print("\nStarting Autonomous Digging Procedure!")
        
        self.cli_digger_setPower.call_async(DiggerSetPower.Request(power=self.digger_rotation_power))
        self.cli_conveyor_setPower.call_async(ConveyorSetPower.Request(drum_belt_power=self.drum_belt_power, conveyor_belt_power=self.conveyor_belt_power))

        self.arduino.read_all()  # Read all messages from the serial buffer to clear them out
        time.sleep(2)  # Wait a bit for the drum motor to get up to speed

        # Tell the Arduino to extend the linear actuator
        self.arduino.write(f"e{chr(self.linear_actuator_speed)}".encode("ascii"))
        while True:  # Wait for a confirmation message from the Arduino
            reading = self.arduino.read()
            print(reading)
            if reading == b"f":
                break

        time.sleep(5)  # Wait for 5 seconds

        # Tell the Arduino to retract the linear actuator
        self.arduino.write(f"r{chr(self.linear_actuator_up_speed)}".encode("ascii"))
        while True:  # Wait for a confirmation message from the Arduino
            reading = self.arduino.read()
            print(reading)
            if reading == b"s":
                break

        # Reverse the digging drum
        self.cli_digger_stop.call_async(Stop.Request())
        self.cli_digger_setPower.call_async(DiggerSetPower.Request(power=-1 * self.digger_rotation_power))

        time.sleep(5)  # Wait for 5 seconds

        self.cli_digger_stop.call_async(Stop.Request())
        self.cli_conveyor_stop.call_async(Stop.Request())

        print("Autonomous Digging Procedure Complete!\n")

    def apriltags_callback(self, msg):
        """Process the Apriltag detections."""
        array = msg.transforms
        entry = array.pop()

        # Create a PoseWithCovarianceStamped object from the Apriltag detection
        pose_object = PoseWithCovarianceStamped()
        pose_object.header = entry.header
        pose_object.pose.pose.position.x = (
            entry.transform.translation.x + self.typeapriltag_camera_offset
        )
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
        self.apriltagX = entry.transform.translation.x + self.typeapriltag_camera_offset
        # Foward-Backward Distance to the tag (measured in meters)
        self.apriltagZ = entry.transform.translation.z
        # Yaw Angle error to the tag's orientation (measured in radians)
        self.apriltagYaw = entry.transform.rotation.y
        # print('x:', self.apriltagX, 'z:', self.apriltagZ, 'yaw:', self.apriltagYaw)

    def joystick_callback(self, msg):
        """This method is called whenever a joystick message is received."""

        # TELEOP CONTROLS BELOW #
        if self.state == states["Teleop"]:
            # Drive the robot using joystick input during Teleop
            drive_power = (
                msg.axes[RIGHT_JOYSTICK_VERTICAL_AXIS] * self.max_drive_power
            )  # Forward power
            turn_power = (
                msg.axes[LEFT_JOYSTICK_HORIZONTAL_AXIS] * self.max_turn_power
            )  # Turning power
            self.drive_power_publisher.publish(Twist(linear=Vector3(x=drive_power), angular=Vector3(z=turn_power)))

            # Check if the digger button is pressed
            if msg.buttons[X_BUTTON] == 1 and buttons[X_BUTTON] == 0:
                self.cli_digger_toggle.call_async(DiggerToggle.Request(power=self.digger_rotation_power))
                self.cli_conveyor_toggle.call_async(ConveyorToggle.Request(drum_belt_power=self.drum_belt_power, conveyor_belt_power=self.conveyor_belt_power))
            # Check if the offloader button is pressed
            if msg.buttons[B_BUTTON] == 1 and buttons[B_BUTTON] == 0:
                self.cli_offloader_toggle.call_async(OffloaderToggle.Request(power=self.offload_belt_power))

            # Check if the digger_extend button is pressed
            if msg.buttons[A_BUTTON] == 1 and buttons[A_BUTTON] == 0:
                self.digger_extend_toggled = not self.digger_extend_toggled
                if self.digger_extend_toggled:
                    # Tell the Arduino to extend the linear actuator
                    self.arduino.write(f"e{chr(self.linear_actuator_speed)}".encode("ascii"))
                else:
                    # Tell the Arduino to retract the linear actuator
                    self.arduino.write(
                        f"r{chr(self.linear_actuator_up_speed)}".encode("ascii")
                    )

            # Stop the linear actuator
            if msg.buttons[Y_BUTTON] == 1 and buttons[Y_BUTTON] == 0:
                # Send stop command to the Arduino
                self.arduino.write(f"e{chr(0)}".encode("ascii"))

            if msg.buttons[RIGHT_BUMPER] == 1 and buttons[RIGHT_BUMPER] == 0:
                # Reverse the digging drum (set negative power)
                self.cli_digger_setPower.call_async(DiggerSetPower.Request(power=-1 * self.digger_rotation_power))
                self.cli_conveyor_toggle.call_async(ConveyorToggle.Request(drum_belt_power=self.drum_belt_power, conveyor_belt_power=self.conveyor_belt_power))

            # NOTE: This hasn't been tested/used yet
            # # Small linear actuator controls
            # if msg.buttons[RIGHT_BUMPER] == 1 and buttons[RIGHT_BUMPER] == 0:
            #   self.arduino.write(f'a{chr(small_linear_actuator_speed)}'.encode(
            #     'ascii'))  # Extend the small linear actuator
            # if msg.buttons[LEFT_BUMPER] == 1 and buttons[LEFT_BUMPER] == 0:
            #   self.arduino.write(f'b{chr(small_linear_actuator_speed)}'.encode(
            #     'ascii'))  # Retract the small linear actuator

        # THE CONTROLS BELOW ALWAYS WORK #

        # Check if the autonomous digging button is pressed
        if msg.buttons[BACK_BUTTON] == 1 and buttons[BACK_BUTTON] == 0:
            if self.state == states["Teleop"]:
                self.state = states["Auto_Dig"]
                self.autonomous_digging_process = multiprocessing.Process(
                    target=self.auto_dig_procedure
                )
                self.autonomous_digging_process.start()  # Start the auto dig process
            elif self.state == states["Auto_Dig"]:
                self.autonomous_digging_process.kill()  # Kill the auto dig process
                print("Autonomous Digging Procedure Terminated\n")
                self.cli_digger_stop.call_async(Stop.Request()) # stop the digging drum
                self.cli_conveyor_stop.call_async(Stop.Request()) # stop the conveyor belts
                self.arduino.write(f"e{chr(0)}".encode("ascii")) # Stop the linear actuator

        # Check if the camera toggle button is pressed
        if msg.buttons[START_BUTTON] == 1 and buttons[START_BUTTON] == 0:
            self.camera_view_toggled = not self.camera_view_toggled
            if (self.camera_view_toggled):  # Start streaming /dev/front_webcam on port 5000
                if self.back_camera is not None:
                    # Kill the self.back_camera process
                    os.killpg(os.getpgid(self.back_camera.pid), signal.SIGTERM)
                    self.back_camera = None
                # self.get_logger().info(f'using ip {self.target_ip}')
                self.front_camera = subprocess.Popen(
                    'gst-launch-1.0 v4l2src device=/dev/front_webcam ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw,format=I420" ! x264enc bitrate=300 tune=zerolatency speed-preset=ultrafast ! "video/x-h264,stream-format=byte-stream" ! h264parse ! rtph264pay ! udpsink host=192.168.1.110 port=5000',
                    shell=True,
                    preexec_fn=os.setsid,
                )
            else:  # Start streaming /dev/back_webcam on port 5000
                if self.front_camera is not None:
                    # Kill the self.front_camera process
                    os.killpg(os.getpgid(self.front_camera.pid), signal.SIGTERM)
                    self.front_camera = None
                # self.get_logger().info(f'using ip {self.target_ip}')
                self.back_camera = subprocess.Popen(
                    'gst-launch-1.0 v4l2src device=/dev/back_webcam ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw,format=I420" ! x264enc bitrate=300 tune=zerolatency speed-preset=ultrafast ! "video/x-h264,stream-format=byte-stream" ! h264parse ! rtph264pay ! udpsink host=192.168.1.110  port=5000',
                    shell=True,
                    preexec_fn=os.setsid,
                )

        # Update button states (this allows us to detect changing button states)
        for index in range(len(buttons)):
            buttons[index] = msg.buttons[index]
            
        # Check if the autonomous digging process has finished
        if self.autonomous_digging_process is not None and not self.autonomous_digging_process.is_alive():
            self.state = states["Teleop"]
            self.autonomous_digging_process = None

def main(args=None):
    """The main function."""
    rclpy.init(args=args)
    print("Hello from the rovr_control package!")

    node = MainControlNode()
    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


# This code does NOT run if this file is imported as a module
if __name__ == "__main__":
    main()
