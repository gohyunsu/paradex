import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.io.capture_pc.data_sender import DataCollector
from paradex.io.capture_pc.ssh import run_script
from paradex.io.capture_pc.command_sender import CommandSender

run_script("python src/validate/data_sender/client.py")

dc = DataCollector()
dc.start()


while True:
    data_dict = dc.get_data()
    for pc_id, data in data_dict.items():
        print(f"PC ID: {pc_id}, Data: {data}")
    time.sleep(1)
