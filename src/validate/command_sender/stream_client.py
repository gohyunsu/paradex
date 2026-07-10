from threading import Event
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.io.capture_pc.data_sender import DataPublisher
from paradex.io.capture_pc.command_sender import CommandReceiver
from paradex.utils.system import pc_name

start_event = Event()
exit_event = Event()
stop_event = Event()    

dp = DataPublisher(name=pc_name)
cr = CommandReceiver({"start": start_event, "exit": exit_event, "stop": stop_event})

start_time = time.time()    
while not exit_event.is_set():
    if start_event.is_set() and not stop_event.is_set():
        dp.send_data([{"name": dp.name, "value": time.time() - start_time}], [])
    time.sleep(0.1)

    if stop_event.is_set():
        print("Stopped")
        start_event.clear()
        stop_event.clear()
        continue
