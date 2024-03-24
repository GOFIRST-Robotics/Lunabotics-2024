import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject

from threading import Thread, Event
import paramiko
from pyroute2 import IPRoute
import keyboard
import sys 
# Initialize GStreamer
Gst.init(None)
print("Creating Pipeline \n ")
pipeline = Gst.Pipeline()

source = Gst.ElementFactory.make("udpsrc", "src")
source.set_property("port", 5000)

caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
caps_v4l2src.set_property('caps', Gst.Caps.from_string("video/x-av1,width=640,height=480,framerate=15/1"))

queue = Gst.ElementFactory.make("queue", "queue")

decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")

sink = Gst.ElementFactory.make("autovideosink", "sink")


print("Adding srcs \n")
pipeline.add(source)
pipeline.add(caps_v4l2src)
pipeline.add(queue)
pipeline.add(decoder)
pipeline.add(sink)

print("Linking srcs \n")
#link the elements
source.link(caps_v4l2src)
caps_v4l2src.link(queue)
queue.link(decoder)
decoder.link(sink)

# Start playing
print("Starting pipeline \n")
pipeline.set_state(Gst.State.PLAYING)

stop_event = Event()
change_source_thread = Thread()
change_source_thread.start()

server = paramiko.SSHClient()
key = paramiko.RSAKey.from_private_key_file("/root/.ssh/id_orin")
server.set_missing_host_key_policy(paramiko.AutoAddPolicy())
remote = "10.133.240.45" #need to make this dynamic
user="blixt"
# get current program ip
with IPRoute() as ipr:
    client = ipr.route('get', dst=remote)[0].get_attr('RTA_PREFSRC')

server.connect(hostname=remote,username=user,pkey=key)
server.get_transport().set_keepalive(1)
cmd = f'python3 Lunabotics-2024/src/gstreamer/gstreamer-server.py {client}'
print(cmd)
stdin, stdout, stderr = server.exec_command(cmd,get_pty=True)
server.get_transport().set_keepalive(1)
def line_buffered(f):
    line_buf = ""
    while not f.channel.exit_status_ready():
        line_buf += f.read(1)
        if line_buf.endswith('\n'):
            yield line_buf
            line_buf = ''

# Run the main loop
print("Running loop")
while True:
    try:
        message:Gst.Message = pipeline.get_bus().timed_pop(Gst.SECOND)
        if message == None:
            pass
        elif message.type == Gst.MessageType.EOS:
            break
        elif message.type == Gst.MessageType.ERROR:
            gi.error("Error", message.parse_error())
            break
    except KeyboardInterrupt:
        break
print("Exiting")
stop_event.set()
pipeline.set_state(Gst.State.NULL)
server.close()
print("Exited")
