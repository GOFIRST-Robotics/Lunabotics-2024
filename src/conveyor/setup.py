import os
from glob import glob
from setuptools import setup

package_name = "conveyor"

setup(
    name=package_name,
    version="0.1.0",
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
    description="This package is for the conveyor subsystem.",
    license="MIT License",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
        "conveyor_node = conveyor.conveyor_node:main", 
        "check_load = conveyor.check_load:main"
        ],
    },
)
