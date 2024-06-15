#!/bin/bash
docker_arg="-v /usr/local/zed/resources:/usr/local/zed/resources -v /ssd:/ssd -v /usr/local/zed/settings:/usr/local/zed/settings"
bash ~/Lunabotics-2024/src/isaac_ros/isaac_ros_common/scripts/run_dev.sh -d ~/Lunabotics-2024 -i ros2_humble.realsense.deepstream.user.zed.umn.gazebo -a "${docker_arg}" -v