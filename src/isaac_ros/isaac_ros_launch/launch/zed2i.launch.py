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

from launch import LaunchDescription
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LoadComposableNodes, Node
from launch_ros.descriptions import ComposableNode
from launch.conditions import UnlessCondition
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

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

    return LaunchDescription(
        [
            robot_state_publisher,
            zed2_container,
            load_composable_nodes,
        ]
    )
