import os
from glob import glob
from setuptools import find_packages, setup

package_name = "gstreamer"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name + "/resource", ["resource/gstreamer-select.ui"]),
        ("share/" + package_name, ["package.xml", "plugin.xml"]),
        (
            os.path.join("share", package_name),
            glob("launch/*launch.[pxy][yma]*", recursive=True),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="blixt",
    maintainer_email="jmblixt3@gmail.com",
    description="Gstreamer straming package for umn robotics",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "server_node = gstreamer.server_node:main",
        ],
    },
)
