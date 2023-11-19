import os
from glob import glob
from setuptools import setup

package_name = "skimmer"

setup(
    name=package_name,
    version="0.2.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name), glob("launch/*launch.[pxy][yma]*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anthony",
    maintainer_email="anthonybrog@gmail.com",
    description="This package is for the skimmer subsystem.",
    license="MIT License",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "skimmer_node = skimmer.skimmer_node:main",
            "ros_check_load = conveyor.ros_check_load:main",
        ],
    },
)
