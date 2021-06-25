#!/usr/bin/env python3
import subprocess
import os

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