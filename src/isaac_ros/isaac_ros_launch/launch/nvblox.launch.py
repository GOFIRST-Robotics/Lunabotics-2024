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


# from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import LoadComposableNodes, Node
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import SetParameter, SetParametersFromFile, SetRemap
from launch_ros.descriptions import ComposableNode
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():

    base_config_dir = PathJoinSubstitution(["config", "nvblox"])
    specialization_dir = PathJoinSubstitution([base_config_dir, "specializations"])

    # Config files
    base_config = PathJoinSubstitution([base_config_dir, "nvblox_base.yaml"])
    zed_config = PathJoinSubstitution([specialization_dir, "nvblox_zed.yaml"])
    gazebo_simulation_config = PathJoinSubstitution([specialization_dir, "nvblox_gazebo_sim.yaml"])

    # Conditionals for setup
    setup_for_zed = IfCondition(LaunchConfiguration("setup_for_zed", default="False"))
    setup_for_gazebo = IfCondition(LaunchConfiguration("setup_for_gazebo", default="False"))

    # Option to attach the nodes to a shared component container for speed ups through intra process communication.
    # Make sure to set the 'component_container_name' to the name of the component container you want to attach to.
    attach_to_shared_component_container_arg = LaunchConfiguration(
        "attach_to_shared_component_container", default=False
    )
    component_container_name_arg = LaunchConfiguration("component_container_name", default="nvblox_container")

    # If we do not attach to a shared component container we have to create our own container.
    nvblox_container = Node(
        name=component_container_name_arg,
        package="rclcpp_components",
        executable="component_container_mt",
        output="screen",
        condition=UnlessCondition(attach_to_shared_component_container_arg),
    )

    load_composable_nodes = LoadComposableNodes(
        target_container=component_container_name_arg,
        composable_node_descriptions=[
            ComposableNode(name="nvblox_node", package="nvblox_ros", plugin="nvblox::NvbloxNode")
        ],
    )

    group_action = GroupAction(
        [
            # Set parameters with specializations
            SetParametersFromFile(base_config),
            SetParametersFromFile(zed_config, condition=setup_for_zed),
            SetParametersFromFile(gazebo_simulation_config, condition=setup_for_gazebo),
            SetParameter(name="global_frame", value=LaunchConfiguration("global_frame", default="odom")),
            # Remappings for zed data
            SetRemap(src=["depth/image"], dst=["/zed2i/zed_node/depth/depth_registered"], condition=setup_for_zed),
            SetRemap(src=["depth/camera_info"], dst=["/zed2i/zed_node/depth/camera_info"], condition=setup_for_zed),
            SetRemap(src=["color/image"], dst=["/zed2i/zed_node/rgb/image_rect_color"], condition=setup_for_zed),
            SetRemap(src=["color/camera_info"], dst=["/zed2i/zed_node/rgb/camera_info"], condition=setup_for_zed),
            SetRemap(src=["pose"], dst=["/zed2i/zed_node/pose"], condition=setup_for_zed),
            # Include the node container
            load_composable_nodes,
        ]
    )

    combine_esdf = Node(
        package="combine_esdf",
        executable="combine_esdf",
        name="combine_esdf",
        parameters=[base_config],
    )

    return LaunchDescription([nvblox_container, group_action, combine_esdf])
