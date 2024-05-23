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


from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # Setup to launch the simulator and Gazebo world
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"])]
        ),
        launch_arguments={
            "gz_args": PathJoinSubstitution([FindPackageShare("gazebo_files"), "worlds", "NASA_field.sdf"])
        }.items(),
    )

    # Takes the description and joint angles as inputs and publishes the 3D poses of the robot links
    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [PathJoinSubstitution([FindPackageShare("robot_description"), "launch", "robot_description.launch.py"])]
        ),
    )

    # Launch Arguments
    run_rviz_arg = DeclareLaunchArgument("run_rviz", default_value="True", description="Whether to start RVIZ")

    # Visualize in RViz
    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", PathJoinSubstitution([FindPackageShare("ros_gz_launch"), "config", "camera.rviz"])],
        condition=IfCondition(LaunchConfiguration("run_rviz")),
    )

    # Bridge ROS topics and Gazebo messages for establishing communication
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[
            {
                "config_file": PathJoinSubstitution([FindPackageShare("ros_gz_launch"), "config", "ros_gz_bridge.yaml"]),
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
