import sys
import gi
import platform
from threading import Thread, Event
from rovr_interfaces.srv import SetClientIp, SetActiveCamera, SetEncoding

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402


class GstreamerServer:

    def __init__(self, ip_srv: SetClientIp, camera_srv: SetActiveCamera, encod_srv: SetEncoding):
        Gst.init(None)
        self.pipeline = Gst.Pipeline()

        camera_src = Gst.ElementFactory.make(camera_srv.srctype, "camera_src")
        if camera_srv.srctype == "videotestsrc":
            print(f"Using videotestsrc{camera_srv.device}")
            camera_src.set_property("pattern", int(camera_srv.device))
        else:
            camera_src.set_property("device", camera_srv.device)
        self.pipeline.add(camera_src)

        nonNVvideoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        self.pipeline.add(nonNVvideoconvert)
        camera_src.link(nonNVvideoconvert)

        caps = Gst.Caps.from_string(
            f"video/x-raw, \
            width=(int){camera_srv.width}, \
            height=(int){camera_srv.height}, \
            framerate=(fraction){camera_srv.framerate}/1, \
            format=(string){camera_srv.format}"
        )
        src_caps = Gst.ElementFactory.make("capsfilter", "src_caps")
        src_caps.set_property("caps", caps)
        self.pipeline.add(src_caps)
        nonNVvideoconvert.link(src_caps)

        if platform.machine() == "aarch64":
            videoconvert = Gst.ElementFactory.make("nvvidconv", "nvvidconv")
        elif platform.machine() == "x86_64" or platform.machine() == "amd64":
            videoconvert = Gst.ElementFactory.make("nvvideoconvert", "nvvideoconvert")
        else:
            sys.exit(1)
        self.pipeline.add(videoconvert)
        src_caps.link(videoconvert)

        udp_sink = Gst.ElementFactory.make("udpsink", "udpsink")
        udp_sink.set_property("host", ip_srv.client_ip)
        udp_sink.set_property("port", 5000)
        self.pipeline.add(udp_sink)

        if encod_srv.encoding == "h265":
            self.init_h265(videoconvert, udp_sink)
        elif encod_srv.encoding == "av1":
            self.init_av1(videoconvert, udp_sink)

    def init_h265(self, input, sink):
        # gst-launch-1.0 videotestsrc ! 'video/x-raw, width=(int)1920, height=(int)1080,
        # format=(string)NV12, framerate=(fraction)30/1' ! nvvideoconvert ! nvv4l2h265enc
        # ! rtph265pay! udpsink host=127.0.0.1 port=5000
        # gst-launch-1.0 videotestsrc ! 'video/x-raw, width=(int)640, height=(int)480,
        # format=(string)NV12, framerate=(fraction)30/1' ! nvvideoconvert ! nvv4l2h265enc
        # ! rtph265pay ! udpsink host=127.0.0.1 port=5000
        nvv4l2h265enc = Gst.ElementFactory.make("nvv4l2h265enc", "nvv4l2h265enc")
        self.pipeline.add(nvv4l2h265enc)
        input.link(nvv4l2h265enc)

        rtph265pay = Gst.ElementFactory.make("rtph265pay", "rtph265pay")
        self.pipeline.add(rtph265pay)
        nvv4l2h265enc.link(rtph265pay)

        rtph265pay.link(sink)

    def init_av1(self, input, sink):
        # gst-launch-1.0 videotestsrc ! 'video/x-raw, width=(int)640, height=(int)480, format=(string)NV12,
        # framerate=(fraction)30/1' ! nvvideoconvert ! nvv4l2av1enc ! udpsink host=127.0.0.1 port=5000
        nvv4l2av1enc = Gst.ElementFactory.make("nvv4l2av1enc", "nvv4l2av1enc")
        nvv4l2av1enc.set_property("bitrate", 1000000)
        self.pipeline.add(nvv4l2av1enc)
        input.link(nvv4l2av1enc)

        nvv4l2av1enc.link(sink)
        pass

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)


if __name__ == "__main__":
    ip = SetClientIp.Request()
    ip.client_ip = "127.0.0.1"
    camera = SetActiveCamera.Request()
    camera.srctype = "videotestsrc"
    camera.device = "0"
    camera.width = 640
    camera.height = 480
    camera.framerate = 30
    camera.format = "NV12"
    encoding = SetEncoding.Request()
    encoding.encoding = "h265"
    server = GstreamerServer(ip, camera, encoding)
    server.run()
    stop_event = Event()
    change_source_thread = Thread()
    change_source_thread.start()
    while True:
        try:
            message: Gst.Message = server.pipeline.get_bus().timed_pop(Gst.SECOND)
            if message is None:
                pass
            elif message.type == Gst.MessageType.EOS:
                break
            elif message.type == Gst.MessageType.ERROR:
                gi.error("Error", message.parse_error())
                break
        except KeyboardInterrupt:
            break
    server.stop()
