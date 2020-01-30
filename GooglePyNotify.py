from __future__ import print_function
import time
import argparse
from urllib import parse as urlparse
import sys
import logging
import socket
import os.path
import pychromecast
from http.server import HTTPServer, SimpleHTTPRequestHandler
from gtts import gTTS

HOST_NAME = "0.0.0.0"
CHROMECASTS = 0

# define the default value of all the parameters
tcp_port = 80
device_name = ""
lang = "en-us"
cache_dir = "mp3_cache"
logname = sys.argv[0] + '.log'
logging.basicConfig(filename=logname,
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

class HttpServer(SimpleHTTPRequestHandler):

	def _set_headers(self):
		self.send_response(200)
		self.send_header('Content-type', 'text/html')
		self.end_headers()

	def do_GET(self):
		# Check For URL Stream "http://IPADDRESS/Notify?"
		global device_name, lang
		if "/Notify?" in self.path:
			self._set_headers()
			parsed = urlparse.parse_qs(urlparse.urlparse(self.path).query)
			device_name = parsed.get('device', [device_name])[0]
			lang = parsed.get('lang', [lang])[0]
			notification = parsed.get('message', [''])[0]

			# Add some error handling for chrome looping
			redir = "<html><head><meta http-equiv='refresh' content='0;url=.\' /></head><body><h1>Notification Sent! <br>"+notification+"</h1></body></html>"
			logging.info(redir)
			self.wfile.write(redir.encode())
			if notification != "":
				self.notify(notification)
			return

		elif "/HelloWorld" in self.path:
			self._set_headers()
			logging.info("Hello World Test")
			self.notify("Hello+World")
			return

		else:
			SimpleHTTPRequestHandler.do_GET(self)

	# POST is for submitting data
	def do_POST(self):

		logging.info( "incomming http: " + self.path )

		content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
		post_data = self.rfile.read(content_length) # <--- Gets the data itself
		self.send_response(200)

	def notify(self, notification):
		if notification == "":
				notification = "No+Notification+Data+Recieved"

		mp3 = cache_dir + "/" + ''.join(e for e in notification if e.isalnum()) + ".mp3"
		text = notification.replace("+"," ")

		if not os.path.isfile(mp3) :
			logging.info("Generating MP3...")
			tts = gTTS(text=text, lang=lang) # See Google TTS API for more Languages (Note: This may do translation Also - Needs Testing)
			tts.save(mp3)
		else:
			logging.info("Reusing MP3...")

		logging.info("Sending notification...")
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Pull IP Address for Local HTTP File Serving (Note: This requires an internet connection)
		s.connect(("8.8.8.8", 80))
		ip_add = s.getsockname()[0]
		print (ip_add)
		s.close()
		self.Cast(ip_add, mp3)

		logging.info("Notification Sent.")

		return

	def Cast(self, ip_add, mp3):
		global tcp_port
		# castdevice = next(cc for cc in CHROMECASTS if cc.device.model_name == "Google Home")
		castdevice = pychromecast.Chromecast(device_name)
		logging.info("Cast device:" + castdevice.device.friendly_name)
		castdevice.wait()
		mediacontroller = castdevice.media_controller # ChromeCast Specific
		url = "http://" + ip_add + ":" + str(tcp_port) + "/" + mp3
		print (url)
		mediacontroller.play_media(url, 'audio/mp3')
		return

# Process command line parameters
parser = argparse.ArgumentParser(description="A http service to provide audio cast to ChromeCast devices")
# [--port <TCP Port>] [--device <Device Name or IP>] [--lang <Default language>] [--cachedir <Cache Directory>]
parser.add_argument('--port', dest='tcp_port', help='TCP Port listen on. Default = 80', type=int, required=False)
parser.add_argument('--device', dest='device_name', help='Specify the name or IP of cast device. Default = <first finded device>', required=False)
parser.add_argument('--lang', dest='lang', help='Specify the default language. Default = en-us', required=False)
parser.add_argument('--cachedir', dest='cache_dir', help='Specify the cache dir used to save generated MP3 files. Default = mp3_cache', required=False)
args = parser.parse_args()
logging.info(args)
if args.tcp_port is not None:
	tcp_port = args.tcp_port
if args.device_name is not None:
	device_name = args.device_name
if args.lang is not None:
	lang = args.lang
if args.cache_dir is not None:
	cache_dir = args.cache_dir

if not os.path.exists(cache_dir):
	os.makedirs(cache_dir)

logging.info("Getting chromecasts...")
CHROMECASTS = pychromecast.get_chromecasts()
# List all the avaliable cast devices
logging.info([cc.device.friendly_name for cc in CHROMECASTS])

if device_name=="":         # if did not specify the device name or IP, we are going to find the first avaliable one
	castdevice = next(cc for cc in CHROMECASTS if cc.device.model_name in ["Google Home", "Google Home Mini", "Google Nest Mini", "Google Home Max"])
	if castdevice is None:      # we failed to find a device
		exit(0)
	else:
		device_name=castdevice.socket_client.host
		# There is a bug introduced in zeroconf 0.24.4 which blocked the DNS resolve
		# So the returned host name will looks like: 'record[a,in-unique,6c898c16-4dc1-6575-e851-3b5d1c994e9e.local.]=120/119,192.168.1.167'
		# Here I use a trick to retrieve the IP address from above host record
		device_name=device_name.split(',')[-1]
logging.info("Default cast device:" + device_name)
logging.info("%s Server Starts - %s:%s", time.asctime(), HOST_NAME, tcp_port)
httpServer = HTTPServer((HOST_NAME, tcp_port), HttpServer) #HTTP Server Stuff (Python Librarys)

try:
	httpServer.serve_forever()
except KeyboardInterrupt:
	pass

httpServer.server_close()
logging.info("%s Server Stops - %s:%s", time.asctime(), HOST_NAME, tcp_port)
