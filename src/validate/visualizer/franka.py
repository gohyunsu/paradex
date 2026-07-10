import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.visualization.visualizer.viser import ViserViewer
from paradex.robot.utils import get_robot_urdf_path

a = ViserViewer()
a.add_robot("franka", get_robot_urdf_path("franka"))
a.start_viewer()
