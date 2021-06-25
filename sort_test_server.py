#!/usr/bin/env python3
import http.server
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import sys
import subprocess
import os
import time

class ServerHandler(SimpleHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        name = self.data_string.decode("utf-8").split('=')[0]
        if name == 'startButton':
            kill_process_key_words = ['lifter', 'moving']
            for key in kill_process_key_words:
                sub = subprocess.Popen(['ps aux | grep {}'.format(key)], shell=True, stdout=subprocess.PIPE)
                output, error = sub.communicate()
                for line in output.splitlines():
                    pid = int(line.split(None)[1])
                    try:
                        os.kill(pid, 9)
                    except:
                        pass
            time.sleep(1)
            subprocess.Popen(['nohup', 'python3', 'lifter_shuttle_test_long_hori.py', '10.0.20.75', '8080', 'F12A01', '400000', '187500', '400000', '400000'],
                    stdout=open('/dev/null', 'w'),
                    stderr=open('logfile.log', 'a'),
                    preexec_fn=os.setpgrp)
        elif name == 'stopButton':
            kill_process_key_words = ['lifter', 'moving']
            for key in kill_process_key_words:
                sub = subprocess.Popen(['ps aux | grep {}'.format(key)], shell=True, stdout=subprocess.PIPE)
                output, error = sub.communicate()
                for line in output.splitlines():
                    pid = int(line.split(None)[1])
                    try:
                        os.kill(pid, 9)
                    except:
                        pass
        SimpleHTTPRequestHandler.do_GET(self)

host_addr = socket.getfqdn() if sys.platform == "darwin" else socket.gethostbyname(socket.gethostname() + ".local")
PORT = 8000
http = HTTPServer((host_addr, PORT), ServerHandler)
print(f'Started http server on {host_addr}:{PORT}')
try:
    http.serve_forever()
except KeyboardInterrupt:
    pass
http.server_close()
print('Stopped http server')