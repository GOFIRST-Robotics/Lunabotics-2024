import os
from rclpy.node import Node, Client
from ament_index_python import get_package_share_directory
from python_qt_binding import loadUi
from python_qt_binding.QtCore import Slot
from python_qt_binding.QtWidgets import QWidget, QComboBox
from rovr_interfaces.srv import SetClientIp, SetActiveCamera, SetEncoding
from .client_gstreamer import GstreamerClient
import rclpy
import socket
import fcntl
import struct
from rqt_py_common.extended_combo_box import ExtendedComboBox


class ClientWidget(QWidget):
    timeout = 2e9  # 2 seconds with nano seconds as unit
    encodings = ["av1", "h265"]

    def __init__(self, node: Node):
        super(ClientWidget, self).__init__()
        self.setObjectName("ClientWidget")
        self.node = node
        self.display_window = GstreamerClient()
        self.display_window.run()
        ui_file = os.path.join(get_package_share_directory("gstreamer"), "resource", "gstreamer-select.ui")
        loadUi(ui_file, self, {"ExtendedComboBox": ExtendedComboBox})
        network_dropdown: QComboBox = self.findChild(QComboBox, "network_dropdown")
        self.add_network_interfaces(network_dropdown)
        encoding_dropdown: QComboBox = self.findChild(QComboBox, "encoding_dropdown")
        self.get_encodings(encoding_dropdown)

        # Call the buttons to set ip and encoding by default
        # self.on_ip_push_button_clicked()
        self.on_encoding_push_button_clicked()

    def add_network_interfaces(self, comboBox: QComboBox):
        for _, interface in socket.if_nameindex():
            if interface != "lo":
                comboBox.addItem(interface)
        comboBox.setCurrentIndex(0)

    def get_encodings(self, comboBox: QComboBox):
        for encoding in self.encodings:
            comboBox.addItem(encoding)
        comboBox.setCurrentIndex(0)

    def get_ip_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        interface = str(self.network_dropdown.currentText())
        return socket.inet_ntoa(
            fcntl.ioctl(
                s.fileno(),
                0x8915,
                struct.pack("256s", interface[:15].encode("utf-8")),  # SIOCGIFADDR
            )[20:24]
        )

    def wait_cli(self, cli: Client, req):
        future = cli.call_async(req)
        start_time = self.node.get_clock().now().nanoseconds

        # Block while waiting for server to respond
        while rclpy.ok() and not future.done() and self.node.get_clock().now().nanoseconds - start_time < self.timeout:
            pass
        if not future.done():
            print("Service Call Failed")
            return

        print("Service Call Returned")
        result = future.result().success
        if result == -1:
            print("No client IP Set")
        elif result == -2:
            print("No encoding set")
        elif result == -3:
            print("No camera selected")

        # self.restart_window()
        self.node.destroy_client(cli)

    @Slot()
    def on_camera1_push_button_clicked(self):
        print("Requesting Camera 1")
        req = SetActiveCamera.Request()
        req.srctype = "v4l2src"
        req.device = "/dev/video0"
        req.width = 640
        req.height = 480
        req.framerate = 30
        req.format = "NV12"
        cli = self.node.create_client(SetActiveCamera, "/set_active_camera")
        self.wait_cli(cli, req)

    @Slot()
    def on_camera2_push_button_clicked(self):
        print("Requesting Camera 2")
        req = SetActiveCamera.Request()
        req.srctype = "v4l2src"
        req.device = "/dev/video5"
        req.width = 640
        req.height = 480
        req.framerate = 30
        req.format = "NV12"
        cli = self.node.create_client(SetActiveCamera, "/set_active_camera")
        self.wait_cli(cli, req)

    @Slot()
    def on_camera3_push_button_clicked(self):
        print("Requesting Camera 3")
        req = SetActiveCamera.Request()
        req.srctype = "v4l2src"
        req.device = "/dev/video7"
        req.width = 640
        req.height = 480
        req.framerate = 30
        req.format = "NV12"
        cli = self.node.create_client(SetActiveCamera, "/set_active_camera")
        self.wait_cli(cli, req)

    @Slot()
    def on_camera4_push_button_clicked(self):
        print("Requesting Camera 4")
        req = SetActiveCamera.Request()
        req.srctype = "v4l2src"
        req.device = "/dev/video6"
        req.width = 640
        req.height = 480
        req.framerate = 30
        req.format = "NV12"
        cli = self.node.create_client(SetActiveCamera, "/set_active_camera")
        self.wait_cli(cli, req)

    @Slot()
    def on_camera5_push_button_clicked(self):
        print("Requesting Camera 5")
        req = SetActiveCamera.Request()
        req.srctype = "v4l2src"
        req.device = "/dev/video4"
        req.width = 640
        req.height = 480
        req.framerate = 30
        req.format = "NV12"
        cli = self.node.create_client(SetActiveCamera, "/set_active_camera")
        self.wait_cli(cli, req)

    def restart_window(self):
        self.display_window.stop()
        self.display_window = GstreamerClient()
        self.display_window.run()

    @Slot()
    def on_ip_push_button_clicked(self):
        req = SetClientIp.Request()
        try:
            req.client_ip = self.get_ip_address()
        except OSError as e:
            print(e)
            return
        cli = self.node.create_client(SetClientIp, "/set_client_ip")
        self.wait_cli(cli, req)

    @Slot()
    def on_encoding_push_button_clicked(self):
        req = SetEncoding.Request()
        req.encoding = str(self.encoding_dropdown.currentText())
        cli = self.node.create_client(SetEncoding, "/set_encoding")
        self.wait_cli(cli, req)
