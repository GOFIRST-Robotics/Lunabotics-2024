import rclpy
from rclpy.node import Node
from std_msgs.msg import *

import pyrealsense2 as rs

YRESOLUTION = 480 # whatever y componenet (vertical) resolution the camera is
XRESOLUTION = 640 # same as above, but in the x direction
DISTANCETHRESH = .25 # how small should the distance between top and conveyor be before offload?
POLLRATE = 1 # Wait time between each distance check
CONSECUTIVECYCLES = 4 # Make sure the reading is consistent

class check_load(Node):

    def __init__(self):
        super().__init__("check_load")
        self.pub = self.create_publisher(Bool, 'readyDump', 10)
        self.prior_checks = []
        self.timer = self.create_timer(POLLRATE, self.publish_distance)
        pipeline = rs.pipeline()

        config = rs.config()
        config.enable_stream(rs.stream.depth, XRESOLUTION, YRESOLUTION, rs.format.z16, 30)
        pipeline.start(config)

    def publish_distance(self):
        try:
            frames = self.pipeline.wait_for_frames()
            depth = frames.get_depth_frane()
            average_tally = 0
            for y in range(YRESOLUTION):
                for x in range(XRESOLUTION):
                    average_tally += depth.get_distance(x, y)
            msg = Bool()
            if len(self.prior_checks) >= CONSECUTIVECYCLES:
                self.prior_checks.pop(0)
            if average_tally / (XRESOLUTION * YRESOLUTION) <= DISTANCETHRESH:
                self.prior_checks.append(True)
            else:
                self.prior_checks.append(False)

            if False not in self.prior_checks and len(self.prior_checks) >= CONSECUTIVECYCLES:
                msg.data = True
            else:
                msg.data = False

            self.pub.publish(msg)

        except Exception as e:
            print(e)
            pass
