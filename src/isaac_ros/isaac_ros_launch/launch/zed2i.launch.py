# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os
from datetime import datetime

from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration, FindExecutable
from launch_ros.actions import LoadComposableNodes, Node
from launch_ros.descriptions import ComposableNode
from launch.conditions import UnlessCondition, IfCondition
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, ExecuteProcess, RegisterEventHandler
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.event_handlers import OnShutdown

from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    bringup_dir = os.path.join("config", "sensors")

    # Config file
    config_file_camera = os.path.join(bringup_dir, "zed2i.yaml")

    config_file_common = os.path.join(bringup_dir, "zed_common.yaml")

    pkg_robot_description = get_package_share_directory("robot_description")

    # Option to attach the nodes to a shared component container for speed ups through intra process communication.
    # Make sure to set the 'component_container_name' to the name of the component container you want to attach to.
    attach_to_shared_component_container_arg = LaunchConfiguration(
        "attach_to_shared_component_container", default=False
    )
    component_container_name_arg = LaunchConfiguration("component_container_name", default="realsense_container")

    record_svo_arg = DeclareLaunchArgument(
        "record_svo",
        default_value="False",
        description="Whether to record ZED data to an SVO file",
    )

    # If we do not attach to a shared component container we have to create our own container.
    zed2_container = Node(
        name=component_container_name_arg,
        package="rclcpp_components",
        executable="component_container_mt",
        output="screen",
        condition=UnlessCondition(attach_to_shared_component_container_arg),
    )

    # Robot State Publisher node (publishing static tfs for the camera)
    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_robot_description, "launch", "robot_description.launch.py"))
    )

    # odom transform
    odom_transform = Node(
        package="isaac_ros_launch",
        executable="odom_publisher",
        name="odom_publisher",
        output="screen",
    )

    load_composable_nodes = LoadComposableNodes(
        target_container=component_container_name_arg,
        composable_node_descriptions=[
            # Zed2 wrapper node
            ComposableNode(
                package="zed_components",
                namespace="zed2i",
                name="zed_node",
                plugin="stereolabs::ZedCamera",
                parameters=[
                    # YAML files
                    config_file_common,  # Common parameters
                    config_file_camera,  # Camera related parameters
                ],
            ),
        ],
    )

    # Get the current date and time
    now = datetime.now()
    # Format as a string
    timestamp_str = now.strftime("%m-%d-%Y_%H:%M:%S")
    # Add the timestamp to the svo filename
    svo_filename = f"/ssd/zed_recording_{timestamp_str}.svo"

    record_svo_srv = ExecuteProcess(
        cmd=[
            [
                FindExecutable(name="ros2"),
                " service call ",
                "/zed2i/zed_node/start_svo_rec ",
                "zed_interfaces/srv/StartSvoRec ",
                f"\"{{compression_mode: 2, bitrate: 10000, svo_filename: '{svo_filename}'}}\"",  # Tune this bitrate to adjust file size
            ]
        ],
        shell=True,
        condition=IfCondition(LaunchConfiguration("record_svo")),
    )

    stop_svo_recording = RegisterEventHandler(
        event_handler=OnShutdown(
            on_shutdown=ExecuteProcess(
                cmd=[
                    [
                        FindExecutable(name="ros2"),
                        " service call ",
                        "/zed2i/zed_node/stop_svo_rec ",
                        "std_srvs/srv/Trigger ",
                    ]
                ],
                shell=True,
                condition=IfCondition(LaunchConfiguration("record_svo")),
            )
        )
    )

    return LaunchDescription(
        [
            record_svo_arg,
            record_svo_srv,
            stop_svo_recording,
            robot_state_publisher,
            zed2_container,
            odom_transform,
            load_composable_nodes,
        ]
    )
