import rclpy
from rclpy.node import Node
from rovr_interfaces.srv import SetClientIp, SetActiveCamera, SetEncoding
from .server_gstreamer import GstreamerServer
import time

class ServerNode(Node):
    g_server: GstreamerServer = None
    ip_srv: SetClientIp = None
    camera_srv: SetActiveCamera = None
    encod_srv: SetEncoding = None
    def __init__(self):
        super().__init__("server")
        self.serv_set_client_ip = self.create_service(
            SetClientIp, "/set_client_ip", self.set_client_ip_callback
        )
        self.serv_set_active_camera = self.create_service(
            SetActiveCamera, "/set_active_camera", self.set_active_camera
        )
        self.serv_set_encoding = self.create_service(
            SetEncoding, "/set_encoding", self.set_encoding
        )

    def set_client_ip_callback(self, request: SetClientIp, response):
        print("recieved ip request")
        self.ip_srv = request
        response.success = self.restart_server()
        return response

    def set_active_camera(self, request: SetActiveCamera, response):
        print("recieved camera request")
        self.camera_srv = request
        response.success = self.restart_server()
        return response
    
    def set_encoding(self, request: SetEncoding, response):
        print("recieved encoding request")
        self.encod_srv = request
        response.success = self.restart_server()
        return response

    def restart_server(self):
        if self.g_server is not None:
            print("Stopping server")
            self.g_server.stop()
            # time.sleep(4) #wait for client to completely start up
        if self.ip_srv is None:
            print("No client ip set")
            return -1
        if self.encod_srv is None:
            print("No encoding set")
            return -2
        if self.camera_srv is None:
            print("No camera set")
            return -3
        self.g_server = GstreamerServer(self.ip_srv, self.camera_srv, self.encod_srv)
        self.g_server.run()
        print("Server restarted")
        return 0

def main(args=None):
    rclpy.init(args=args)
    server = ServerNode()
    rclpy.spin(server)
    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    server.destroy_node()
    rclpy.shutdown()
