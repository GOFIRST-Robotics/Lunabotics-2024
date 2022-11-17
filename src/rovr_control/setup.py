from setuptools import setup

package_name = 'rovr_control'

setup(
    name=package_name,
    version='0.0.3',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Anthony',
    maintainer_email='anthonybrog@gmail.com',
    description='This package is for the main robot control loop.',
    license='MIT License',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'main_control_node = rovr_control.main_control_node:main'
        ],
    },
)