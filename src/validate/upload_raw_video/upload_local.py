import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.video.raw_video_processor import RawVideoProcessor

rvp = RawVideoProcessor()
rvp.process()
rvp.wait_and_monitor()
