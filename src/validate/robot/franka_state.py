"""Non-motion Franka FR3 controller smoke test.

Requires ROS 2 Humble and the franka_ros2 workspace to be sourced, with the
robot stack already running. This script does not send a trajectory goal; it
only checks that the controller can read joint state and TF.

Usage:
    python src/validate/robot/franka_state.py
    python src/validate/robot/franka_state.py --auto_ready
"""

import argparse
import os
import sys
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from paradex.io.robot_controller.franka_controller import (
    EEF_FRAME,
    BASE_FRAME,
    FrankaController,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--auto_ready",
        action="store_true",
        help="Allow FrankaController to cycle ros2_control state if effort is not ready.",
    )
    args = parser.parse_args()

    controller = FrankaController(
        connect_timeout=args.timeout,
        auto_ready=args.auto_ready,
    )
    try:
        data = controller.get_data()
        qpos = np.asarray(data["qpos"])
        eef = np.asarray(data["position"])
        if qpos.shape != (7,):
            raise RuntimeError(f"expected qpos shape (7,), got {qpos.shape}")
        if eef.shape != (4, 4):
            raise RuntimeError(f"expected eef shape (4, 4), got {eef.shape}")

        print(f"qpos: {np.round(qpos, 4).tolist()}")
        print(f"eef: {BASE_FRAME} -> {EEF_FRAME}")
        print(np.array2string(eef, precision=4, suppress_small=True))
        print("PASS: Franka state and TF are readable")
    finally:
        controller.end()


if __name__ == "__main__":
    main()
