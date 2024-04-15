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
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

from launch_ros.actions import Node


def generate_launch_description():
    # Configure ROS nodes for launch

    # Setup project paths
    pkg_project_bringup = get_package_share_directory("ros_gz_launch")
    pkg_project_gazebo = get_package_share_directory("gazebo_files")
    pkg_ros_gz_sim = get_package_share_directory("ros_gz_sim")
    pkg_robot_description = get_package_share_directory("robot_description")

    # Setup to launch the simulator and Gazebo world
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, "launch", "gz_sim.launch.py")),
        launch_arguments={
            "gz_args": PathJoinSubstitution([pkg_project_gazebo, "worlds", "NASA_field.sdf"])
        }.items(),
    )

    # Takes the description and joint angles as inputs and publishes the 3D poses of the robot links
    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_robot_description, "launch", "robot_description.launch.py"))
    )

    # Launch Arguments
    run_rviz_arg = DeclareLaunchArgument("run_rviz", default_value="True", description="Whether to start RVIZ")

    # Visualize in RViz
    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", os.path.join(pkg_project_bringup, "config", "camera.rviz")],
        condition=IfCondition(LaunchConfiguration("run_rviz")),
    )

    # Bridge ROS topics and Gazebo messages for establishing communication
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[
            {
                "config_file": os.path.join(pkg_project_bringup, "config", "ros_gz_bridge.yaml"),
                "qos_overrides./tf_static.publisher.durability": "transient_local",
            }
        ],
        output="screen",
    )

    drivetrain = Node(
        package="drivetrain",
        executable="drivetrain_node",
        name="drivetrain_node",
        parameters=["config/drivetrain_config.yaml", "config/motor_control.yaml", {"GAZEBO_SIMULATION": True}],
        output="screen",
        emulate_tty=True,
    )

    return LaunchDescription([run_rviz_arg, gz_sim, bridge, drivetrain, robot_state_publisher, rviz])
