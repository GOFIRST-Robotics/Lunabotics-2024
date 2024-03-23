import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst, GObject
import sys
import signal
import paramiko
import threading
import socket
from pyroute2 import IPRoute

def sigint_handler(sig, frame):
    print("\n Exiting\n ")
    server.close()
    pipeline.set_state(Gst.State.NULL)
    sys.exit(0)

# Initialize GStreamer
Gst.init(None)
print("Creating Pipeline \n ")
pipeline = Gst.Pipeline()
signal.signal(signal.SIGINT, sigint_handler)

if not pipeline:
    print(" Unable to create Pipeline \n")

source = Gst.ElementFactory.make("udpsrc", "src")
if not source:
    print(" Unable to create Source \n")

caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")

if not caps_v4l2src:
    print(" Unable to create v4l2src capsfilter \n")

queue = Gst.ElementFactory.make("queue", "queue")

if not queue:
    print(" Unable to create Queue \n")

decoder = Gst.ElementFactory.make("nvv4l2decoder", "decoder")

if not decoder:
    print(" Unable to create Decoder \n")

sink = Gst.ElementFactory.make("nveglglessink", "sink")

if not sink:
    print(" Unable to create Sink \n")

source.set_property("port", 5000)
caps_v4l2src.set_property('caps', Gst.Caps.from_string("video/x-av1,width=640,height=480,framerate=15/1"))

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


server = paramiko.SSHClient()
key = paramiko.RSAKey.from_private_key_file("/root/.ssh/id_orin")
server.set_missing_host_key_policy(paramiko.AutoAddPolicy())
remote = "10.133.240.45" #need to make this dynamic
user="rovr-orin"
# get current program ip
with IPRoute() as ipr:
    client = ipr.route('get', dst=remote)[0].get_attr('RTA_PREFSRC')

server.connect(hostname=remote,username=user,pkey=key)
server.get_transport().set_keepalive(1)
cmd = f'gst-launch-1.0 videotestsrc ! "video/x-raw,width=640,height=480,framerate=15/1" ! nvvidconv ! "video/x-raw(memory:NVMM),format=NV12" ! nvv4l2av1enc bitrate=200000 ! "video/x-av1" ! udpsink host={client} port=5000'
print(cmd)
stdin, stdout, stderr = server.exec_command(cmd)
# def line_buffered(f):
#     line_buf = ""
#     while not f.channel.exit_status_ready():
#         line_buf += f.read(1)
#         if line_buf.endswith('\n'):
#             yield line_buf
#             line_buf = ''

# for l in line_buffered(stdout):
#     print (l)

# stdout_thread = threading.Thread(target=(lambda stdout: sys.stdout.write(stdout.read())), args=(stdout,))
# stderr_thread = threading.Thread(target=(lambda stderr: sys.stderr.write(stderr.read())), args=(stderr,))
# stdout_thread.start()
# stderr_thread.start()
# Run the main loop
print("Running loop \n")
loop = GLib.MainLoop()
loop.run()

print("Should never read here\n")
