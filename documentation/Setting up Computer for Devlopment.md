# Required Programs

## Git

#### For Linux/Mac:
You should install git with your distribution's package manager. 
`sudo apt install git`\
`sudo pacman -S git`\
`brew install git`

#### For Windows
Installer found here: https://git-scm.com/install/windows
All the default options should be fine.

## Docker

#### For Linux/Mac
`sudo apt install docker`\
`sudo pacman -S docker`\
`brew install --cask docker`

Run `systemctl status docker` to see if the Docker daemon is running. If it is not run `systemctl start docker`. If Docker is not enabled then it will need to be manually started every time your computer reboots, if you would prefer it starting on boot run `systemctl enable docker`.

#### For Windows
Installer found here: https://docs.docker.com/desktop/setup/install/windows-install/
If you do not already have WSL installed you will need to run the following command in powershell as administrator: `wsl --install`
A reboot will be required for it to take effect.
After installing WSL in Docker go to Settings -> Resources -> WSL integration, and enable it.
You may be required to open up docker desktop to get the Docker daemon running or to reenable WSL. Besides this the Docker desktop is not required for interacting with the containers.

To access controllers through WSL USBIPD-WIN must be installed.
`winget install --interactive --exact dorssel.usbipd-win`

Run `./scripts/enable_joysticks_windows.ps1` in a powershell terminal to allow WSL to access plugged in controllers. You may need to rerun this at times. Run `ls /dev/input/by-id` to see if WSL can access the controllers. File names with 'Logitech Controller' and 'Stream Deck' in them should be seen.

## Zig & ZLS

**Zig Version 0.16 is absolutely required, double check the version after installation!**

If you are using VSCode then you do not have to separately install Zig or ZLS. Instead install the Zig extension https://marketplace.visualstudio.com/items?itemName=ziglang.vscode-zig.

First see if you are able to install via CLI (including windows): https://ziglang.org/learn/getting-started/#managers.

If you are on Linux your distribution's package manager may or may not have Zig, and even if it does it may be an old version.

Here is the raw downloads page if none of the above are possible: https://ziglang.org/download/

Run `zig version` to double check version 0.16 is installed. For convenience add Zig to path.

#### Zig Language Server (ZLS)

ZLS's website has tutorials on how to set it up for many IDEs and how to install: https://zigtools.org/zls/install/.
If you are using the VSCode extension mentioned previously it should work out of the box. ZLS is closely coupled with Zig so its version must specifically support the version of Zig being used.

# Setting up Environment

## Cloning Repository
Run `git clone https://github.com/GOFIRST-Robotics/Lunabotics.git`

There are multiple sub git repositories that must be initialized, run the following (inside of the repo): `git submodule update --init --recursive`

Run `git config --global core.autocrlf true`. Windows and Linux encode the end of lines differently. This option accounts for that issue.

## Running Docker
The purpose of the docker image is to ensure everyone is developing in the same environment. Some of the robot code is also directly tied to the Linux kernel and Windows machines are not able to directly run it.

There are two docker images that can be found in the docker folder, Dockerfile.umn and Dockerfile.dev. Dockerfile.umn (aka the isaac_ros_container) requires a computer with an Nvidia GPU and runs the camera code that requires GPU acceleration, this is the container that actually runs on the Jetson. Since not everyone has a Nvidia GPU there is also a Dockerfile.dev. This docker file includes all of the necessary libraries, commands and environment variables to run some of the ROS2 and all of the Zig code. This is what most people will use.

### Managing Development Container
To start the dev container run `./scripts/enter_dev_container.sh`.

If you wish to change the image or think you accidentally messed up the environment then you will have to manually delete the image or the container. The shell script should automatically build the image or start the container if either do not already exist. However it will not detect if the Dockerfile.dev has been changed and rebuild.

To delete the container run `docker rm -f lunabotics_dev`. If you messed up the environment (like deleting a library) run this command and rerun `enter_dev_container.sh`.

To delete the image run `docker rmi lunabotics_dev && docker rm -f lunabotics_dev`. You should do this if you want to force a rebuild when running `enter_dev_container.sh`.

### Creating VCAN Interface
To allow for debugging CAN while not actually being on the robot you can create a virtual CAN interface that will act like the real thing. Run `./scripts/vcan_startup.sh` (in the container) and it will create the two virtual CAN interfaces called can0 and can1. Rerunning this command may be necessary if the container is killed. You should see the VCAN interfaces when running the command `ip addr`. 

If on the Jetson run `./scripts/can_start.sh` to create actual CAN interfaces.

# Building and Running the Project
There are two parts of the code that run separably, ROS2 and Zig.

## Zig
To build:
`zig build`

To run the controller client:
`./zig-out/bin/client <ip address>`\
Running the client executable may require `sudo` on Windows under WSL.

To run the robot code:
`./zig-out/bin/MFR_local`
 
Note that MFR_jetson is also in the bin. This is the same as MFR_local however it is compiled for the Jetson's architecture and is given a different config file (see src/MFR). The purpose of also producing this executable is to make testing on the Jetson possible without having to pull down your own branch and recompiling. The executable is stand alone so simply copying it over and running it in the container is possible.

If build times get too long you can run specify the first argument 'client', 'local' or 'jetson' to just build their respective executables. However incremental build times should not take too long with Zig.