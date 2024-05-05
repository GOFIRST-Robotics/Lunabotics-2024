#!/bin/bash

source install/setup.bash && \
ros2 run joy joy_node --ros-args --params-file config/joy_node.yaml