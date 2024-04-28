from setuptools import find_packages, setup
import os
from glob import glob

package_name = "isaac_ros_launch"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name),
            glob("launch/*launch.[pxy][yma]*", recursive=True),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Jonathan Blixt",
    maintainer_email="jmblixt3@gmail.com",
    description="Package for ISAAC_ROS launch files",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "frame_id_renamer = isaac_ros_launch.frame_id_renamer:main",
            "odom_publisher = isaac_ros_launch.odom_publisher:main",
        ],
    },
)
