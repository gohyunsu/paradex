import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.io.capture_pc.data_sender import DataPublisher
from paradex.utils.system import pc_name

dp = DataPublisher(name=pc_name)

start_time = time.time()
while True:
    dp.send_data([{"name": dp.name, "value": time.time() - start_time}], [])
    time.sleep(0.5)
