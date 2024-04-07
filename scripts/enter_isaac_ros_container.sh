#!/bin/bash

printf "CONFIG_IMAGE_KEY=ros2_humble.realsense.user.zed.umn.gazebo \n" > ~/Lunabotics-2024/src/isaac_ros/isaac_ros_common/scripts/.isaac_ros_common-config && \
echo "-v /usr/local/zed/resources:/usr/local/zed/resources" > ~/Lunabotics-2024/src/isaac_ros/isaac_ros_common/scripts/.isaac_ros_dev-dockerargs && \
cd ~/Lunabotics-2024/src/isaac_ros/isaac_ros_common/docker && \
../scripts/run_dev.sh ~/Lunabotics-2024