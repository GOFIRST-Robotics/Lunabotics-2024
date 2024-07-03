#!/bin/bash
#
# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
ROOT="src/isaac_ros/isaac_ros_common/scripts"
source $ROOT/utils/print_color.sh

PLATFORM="$(uname -m)"
BASE_NAME="isaac_ros_dev-$PLATFORM"
CONTAINER_NAME="$BASE_NAME-container-$USER"

# Read and parse config file if exists
#
# CONFIG_IMAGE_KEY (string, can be empty)
if [[ -f "${ROOT}/.isaac_ros_common-config" ]]; then
    . "${ROOT}/.isaac_ros_common-config"
fi

# Build image
IMAGE_KEY=ros2_humble
if [[ ! -z "${CONFIG_IMAGE_KEY}" ]]; then
    IMAGE_KEY=$CONFIG_IMAGE_KEY
fi

BASE_IMAGE_KEY=$PLATFORM.user
if [[ ! -z "${IMAGE_KEY}" ]]; then
    BASE_IMAGE_KEY=$PLATFORM.$IMAGE_KEY

    # If the configured key does not have .user, append it last
    if [[ $IMAGE_KEY != *".user"* ]]; then
        BASE_IMAGE_KEY=$BASE_IMAGE_KEY.user
    fi
fi

print_info "Building $BASE_IMAGE_KEY base as image: $BASE_NAME using key $BASE_IMAGE_KEY"
$ROOT/build_base_image.sh $BASE_IMAGE_KEY $BASE_NAME '' '' ''

if [ $? -ne 0 ]; then
    print_error "Failed to build base image: $BASE_NAME, aborting."
    exit 1
fi

docker tag $BASE_NAME umnrobotics/isaac_ros
