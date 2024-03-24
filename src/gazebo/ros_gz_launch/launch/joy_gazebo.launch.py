# Copyright 2022 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node


def generate_launch_description():
    # Configure ROS nodes for launch

    # Setup project paths
    pkg_project_bringup = get_package_share_directory("ros_gz_launch")

    competition_field = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_project_bringup, "launch", "competition_field.launch.py"))
    )

    rovr_control = Node(
        package="rovr_control",
        executable="main_control_node",
        name="rovr_control_node",
        # parameters=["config/drivetrain_config.yaml", "config/motor_control.yaml",
        #             {"GAZEBO_SIMULATION": True}],
        output="screen",
        emulate_tty=True,
    )

    joy = Node(
        package="joy",
        executable="joy_node",
        name="joystick_node",
        output="screen",
        emulate_tty=True,
    )

    return LaunchDescription([competition_field, rovr_control, joy])
