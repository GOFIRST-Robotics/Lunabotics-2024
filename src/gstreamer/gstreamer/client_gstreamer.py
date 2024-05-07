from threading import Thread, Event
import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

class GstreamerClient:
    def __init__(self):
        # Initialize GStreamer
        Gst.init(None)
        # print("Creating Pipeline")
        self.pipeline = Gst.Pipeline()

        source = Gst.ElementFactory.make("udpsrc", "src")
        source.set_property("port", 5000)

        queue = Gst.ElementFactory.make("queue", "queue")
        self.pipeline.add(queue)

        vid_conv = Gst.ElementFactory.make("nvvideoconvert", "vid_conv")
        self.pipeline.add(vid_conv)

        sink = Gst.ElementFactory.make("ximagesink", "sink")
        self.pipeline.add(sink)

        self.pipeline.add(source)
        encoding = "av1"
        if encoding == "h265":
            self.init_h265(source, queue)
        elif encoding == "av1":
            self.init_av1(source, queue)

        decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")
        self.pipeline.add(decoder)
        queue.link(decoder)

        decoder.link(vid_conv)
        vid_conv.link(sink)

    def init_h265(self, source, queue):
        # gst-launch-1.0 udpsrc port=5000 ! "application/x-rtp,payload=96" ! rtph265depay ! h265parse ! queue ! nvv4l2decoder ! nveglglessink
        caps_udp = Gst.ElementFactory.make("capsfilter", "caps_udp")
        caps_udp.set_property(
            "caps", Gst.Caps.from_string("application/x-rtp,payload=96")
        )
        self.pipeline.add(caps_udp)
        source.link(caps_udp)

        rtph265depay = Gst.ElementFactory.make("rtph265depay", "rtph265depay")
        self.pipeline.add(rtph265depay)
        caps_udp.link(rtph265depay)

        h265parse = Gst.ElementFactory.make("h265parse", "h265parse")
        self.pipeline.add(h265parse)
        rtph265depay.link(h265parse)

        h265parse.link(queue)

    def init_av1(self, source, queue):
        # gst-launch-1.0 udpsrc port=5000 ! "video/x-av1,width=640,height=480,framerate=30/1" ! queue ! nvv4l2decoder ! nvvideoconvert ! ximagesink
        caps_v4l2src = Gst.ElementFactory.make("capsfilter", "caps_v4l2src")
        caps_v4l2src.set_property(
            "caps",
            Gst.Caps.from_string("video/x-av1,width=640,height=480,framerate=30/1"),
        )
        self.pipeline.add(caps_v4l2src)
        source.link(caps_v4l2src)

        caps_v4l2src.link(queue)

    def run(self):
        # Start playing
        print("Starting pipeline")
        self.pipeline.set_state(Gst.State.PLAYING)

        self.stop_event = Event()
        change_source_thread = Thread()
        change_source_thread.start()
        
    def stop(self):
        self.stop_event.set()
        self.pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    client = GstreamerClient()
    client.run()
    stop_event = Event()
    change_source_thread = Thread()
    change_source_thread.start()
    while True:
        try:
            message:Gst.Message = client.pipeline.get_bus().timed_pop(Gst.SECOND)
            if message is None:
                pass
            elif message.type == Gst.MessageType.EOS:
                break
            elif message.type == Gst.MessageType.ERROR:
                gi.error("Error", message.parse_error())
                break
        except KeyboardInterrupt:
            break
    client.stop()