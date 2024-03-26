import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject
from threading import Thread, Event
import sys
import signal
import paramiko
import threading
import socket

def change_source():
    while not stop_event.is_set():
        stop_event.wait(2)

        if stop_event.is_set() or len(input_selector_sink_pads) == 1:
            break

        for i,pad in enumerate(input_selector_sink_pads):
            if pad.get_property("active"):
                #Go to next sink
                next_pad = (i+1)%len(input_selector_sink_pads)
                print(f"switch to {next_pad}")
                input_selector.set_property("active-pad", input_selector_sink_pads[next_pad])
                break

# cmd = f'gst-launch-1.0 videotestsrc !  nvvidconv ! "video/x-raw(memory:NVMM),format=NV12" ! nvv4l2av1enc bitrate=200000 ! "video/x-av1" ! udpsink host={client} port=5000'
Gst.init(None)
print("Creating Pipeline")
pipeline = Gst.Pipeline()

input_selector = Gst.ElementFactory.make("input-selector", "input-selector")

src_mounts = ['/dev/video8']
input_selector_sink_pads = []
# Init pads
for i in range(len(src_mounts)):
    currentsink = input_selector.get_request_pad(f"sink_{i}")
    input_selector_sink_pads.append(currentsink)
input_selector.set_property("active-pad", input_selector_sink_pads[0])
pipeline.add(input_selector)

# Init src
for i,mount in enumerate(src_mounts):
    currentsrc = Gst.ElementFactory.make("v4l2src", f"videosrc{i}")
    currentsrc.set_property("device", mount)
    currentpad = currentsrc.get_static_pad("src")
    pipeline.add(currentsrc)
    currentpad.link(input_selector_sink_pads[i])

v4l2src_caps = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
v4l2src_caps.set_property('caps', Gst.Caps.from_string("video/x-raw,width=640,height=480,framerate=15/1"))

nvvidconv = Gst.ElementFactory.make("nvvidconv","nvvidconv")
nvvidconv_caps = Gst.ElementFactory.make("capsfilter", "nvvidconv_caps")
nvvidconv_caps.set_property('caps',Gst.Caps.from_string("video/x-raw(memory:NVMM)format=NV12"))

nvv4l2av1enc = Gst.ElementFactory.make("nvv4l2av1enc","nvv4l2av1enc")
nvv4l2av1enc.set_property("bitrate", 200000)

udpenc_caps = Gst.ElementFactory.make("capsfilter", "udpenc_caps")
udpenc_caps.set_property('caps', Gst.Caps.from_string("video/x-av1"))

udp_sink = Gst.ElementFactory.make("udpsink", "udpsink")
client = sys.argv[1] if len(sys.argv) != 1 else "10.21.47.9"
udp_sink.set_property('host', client)
udp_sink.set_property('port', 5000)

pipeline.add(v4l2src_caps)
pipeline.add(nvvidconv)
pipeline.add(nvvidconv_caps)
pipeline.add(nvv4l2av1enc)
pipeline.add(udpenc_caps)
pipeline.add(udp_sink)

input_selector.link(v4l2src_caps)
v4l2src_caps.link(nvvidconv)
nvvidconv.link(nvvidconv_caps)
nvvidconv_caps.link(nvv4l2av1enc)
nvv4l2av1enc.link(udpenc_caps)
udpenc_caps.link(udp_sink)


print("Starting Pipeline")
pipeline.set_state(Gst.State.PLAYING)

stop_event = Event()
change_source_thread = Thread(target=change_source)
change_source_thread.start()

while True:
    try:
        message:Gst.Message = pipeline.get_bus().timed_pop(Gst.SECOND)
        if message == None:
            pass
        elif message.type == Gst.MessageType.EOS:
            break
        elif message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print("Error: %s" % err, debug)
            break
    except KeyboardInterrupt:
        break
print("exit")
stop_event.set()
pipeline.set_state(Gst.State.NULL)