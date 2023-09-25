# Lunabotics-2024

The official NASA Lunabotics 2024 repository for University of Minnesota Robotics.

![Control-Flow Diagram](assets/NASA-Lunabotics-Software-Diagram.png)

## How to Run Inside Docker Container

Open this repository in vscode then run ctrl-shift-p and type "Remote-Containers: Reopen in Container".
Just press "from dockerfile" and then it will build the container and run it.

When open, run the following commands in the terminal:

```
colcon build --symlink-install
source install/setup.sh
```

If your machine does not have an Nvidia GPU, build using this command instead:

```
colcon build --symlink-install --packages-skip-regex zed*
```

If you need to rebuild the remote container, uncomment the sections in devcontainer that reference remote, then run the following command with the devcontainer cli installed:

```
devcontainer build --push true --workspace-folder . --platform="linux/amd64,linux/arm64" --image-name "umnrobotics/ros"
```

## ROS 2 General Workspace Tips

Make sure to `source install/setup.bash` in every new terminal.

Run `rosdep install -i --from-path src --rosdistro $ROS_DISTRO -y` to install package dependencies.

Run `rm -r build install log` to clean your workspace.

To configure Sonarlint for C++ linting, run the following command:
```
colcon build --symlink-install --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=1
```
Then, point Sonarlint to the `compile_commands.json` file that is created in your `build` directory.

To normalize line endings in git, use the command:
```
git config --global core.autocrlf true
```

## Unity Integration

Start the connection by running:

```
ros2 launch ros_tcp_endpoint endpoint.py ROS_IP:=127.0.0.1
```

## Joystick Node

```
ros2 run joy joy_node --ros-args --params-file config/joy_node.yaml
```

## Apriltag Detection Setup

Follow [this](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_apriltag/blob/main/docs/tutorial-usb-cam.md) tutorial to set up Apriltag detection on your machine.

## Gstreamer Commands

Start Gstreamer H.264 Encoding (On Nvidia Jetson Orin Nano): 

```
gst-launch-1.0 v4l2src device=/dev/video0 ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw,format=I420" ! x264enc bitrate=300 tune=zerolatency speed-preset=ultrafast ! "video/x-h264,stream-format=byte-stream" ! h264parse ! rtph264pay ! udpsink host=127.0.0.1 port=5000
```

Start Gstreamer H.264 Decoding (On Nvidia Jetson Orin Nano): 

```
gst-launch-1.0 udpsrc port=5000 ! "application/x-rtp,payload=96" ! rtph264depay ! h264parse ! avdec_h264 ! nvvidconv ! xvimagesink
```

Start Gstreamer H.265 Decoding (On Ubuntu Laptop): 

```
gst-launch-1.0 udpsrc port=5000 ! application/x-rtp, encoding-name=H265, payload=96 ! rtph265depay ! h265parse ! nvh265dec ! xvimagesink sync=false
```

Start Gstreamer H.264 Decoding (On Ubuntu Laptop): 

```
gst-launch-1.0 udpsrc port=5000 ! application/x-rtp, encoding-name=H264, payload=96 ! rtph264depay ! h264parse ! nvh264dec ! videoflip method=vertical-flip ! xvimagesink sync=false
```

(Change the /dev/video device to add more webcams, and the port number to stream multiple webcams at once)

## Useful Resources/References

[VESC CAN Status Frames Spreadsheet](https://github.com/codermonkey42/VESC_CAN)
