# Franka FR3 Setup Notes

Status checked: 2026-07-10.

This document records the current state of Franka support in the `gohyunsu/paradex`
fork and the recommended path to run the Paradex pipeline with a Franka FR3 arm.

## Current Status

This fork now includes the Franka-specific controller and hand-eye entry points
ported from `origin/vlm_dex`. The code path is present, but real hardware motion
still requires a sourced ROS 2 / `franka_ros2` stack and supervised robot checks.

What is already present:

- `rsc/robot/franka.urdf`: FR3 arm URDF for FK, visualization, and planning-side work.
- `src/validate/visualizer/franka.py`: URDF/Viser smoke test. This does not move hardware.
- `paradex/io/robot_controller/franka_controller.py`: ROS 2 controller wrapper for
  `/fr3_arm_controller/follow_joint_trajectory`.
- `get_arm("franka")`: returns `FrankaController`.
- `src/capture/robot/franka_home.py`, `franka_teaching.py`, and
  `franka_replay_check.py`: home, teaching, and motion dry-run utilities.
- `src/calibration/handeye/capture.py --arm franka`: replays taught poses and captures
  camera images plus `qpos.npy` / `eef.npy`.
- `src/calibration/handeye/calculate.py --arm franka`: uses `fr3_link8` for FK.
- `system/paradex2/network.json` and `system/robothome/network.json`: existing `franka`
  IP entries.
- `paradex/transforms/coordinate.py`: `franka` frame entries.
- `paradex/retargetor/unimanual.py`: accepts `arm_name="franka"` at the retargeting API
  boundary.

What is still not validated by static tests:

- ROS 2 stack availability on the target main PC.
- `FrankaController` construction against a live `/controller_manager`.
- Actual home/replay/capture motion with the FR3 workspace cleared.
- A checked-in `system/current/` runtime config. The loader reads
  `system/current/network.json` and `system/current/pc.json` at import time.

## Recommended Architecture

Use `franka_ros2` as the hardware control backend and keep Paradex at the same
controller abstraction used by xArm:

```text
Paradex script
  -> get_arm("franka") / FrankaController
  -> rclpy action client
  -> /fr3_arm_controller/follow_joint_trajectory
  -> franka_ros2 / libfranka / FCI
```

The controller should expose the same minimal surface expected by existing
calibration and capture scripts:

- `move(qpos, is_servo=False)` for blocking 7-DoF joint trajectory moves.
- `get_data()` returning `{"qpos": (7,), "position": (4,4), "time": float}`.
- `end(...)` for cleanup.

State should be read by name, not index:

- joints: `fr3_joint1` through `fr3_joint7`
- joint state topic: `/joint_states`
- base frame: `fr3_link0`
- end-effector frame: `fr3_link8`

## Host and Robot Setup

Expected FR3/FCI network setup:

- Franka Desk / robot FCI address: `172.16.1.11`
- Main PC NIC on the same subnet, for example `172.16.1.6/24`
- Desk URL: `https://172.16.1.11/desk/`

Before every robot session:

1. Put the robot in Execution mode.
2. Unlock joints.
3. Activate FCI in Franka Desk.
4. Make sure the end-effector load in Desk matches the real hardware.
5. Allow robot UDP through the firewall:

```bash
sudo ufw allow from 172.16.1.11
```

ROS 2 launch pattern:

```bash
source /opt/ros/humble/setup.bash
source ~/franka_ros2_ws/install/setup.bash

ros2 launch franka_fr3_moveit_config moveit.launch.py \
  robot_ip:=172.16.1.11 \
  use_fake_hardware:=false \
  load_gripper:=false
```

Sanity checks:

```bash
ros2 control list_controllers -c /controller_manager
ros2 topic echo --once /joint_states
ros2 run tf2_ros tf2_echo fr3_link0 fr3_link8
python src/validate/robot/franka_state.py
```

If the conda env shadows the system `libstdc++`, ROS imports can fail with a
`GLIBCXX_3.4.30` error. On this host, the working pattern for base ROS imports is:

```bash
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 python src/validate/robot/franka_state.py
```

`franka_teaching.py` also requires `franka_msgs`, which should come from the
`franka_ros2` workspace. If `~/franka_ros2_ws/install/setup.bash` is missing,
install/build/source that workspace before teaching.

## Paradex Config

Create or link `system/current/` for the machine that will run the pipeline. The
current loader imports:

```text
system/current/network.json
system/current/pc.json
system/current/camera.json
system/current/charuco_info.json
```

For Franka, prefer the xArm-style structure even though the current
`FrankaController` talks through ROS 2 and does not read `robot_ip` directly:

```json
{
  "franka": {
    "name": "franka",
    "param": {
      "robot_ip": "172.16.1.11"
    }
  }
}
```

Keep the entry anyway so scripts can identify the arm consistently.

## Pipeline Order

The Franka path is:

1. Start camera daemons on capture PCs.
2. Start the Franka ROS 2 stack on the main PC.
3. Run a non-motion state readback:

```bash
python src/validate/robot/franka_state.py
```

4. Teach hand-eye poses:

```bash
python src/capture/robot/franka_teaching.py
```

5. Replay motion without cameras:

```bash
python src/capture/robot/franka_replay_check.py --step --home
```

6. Capture multi-camera hand-eye data:

```bash
python src/calibration/handeye/capture.py --arm franka
```

7. Solve without ROS in `PYTHONPATH` if ROS Pinocchio conflicts with the conda
   Pinocchio/Numpy stack:

```bash
PYTHONPATH= python src/calibration/handeye/calculate.py --arm franka
```

8. Validate C2R with robot overlays before collecting task data.

## Known Risks

- `DEVICE2WRIST["franka"]` is currently documented as non-orthonormal. Fix or
  validate it before relying on retargeted teleop actions.
- Franka FCI requires stable 1 kHz control timing. If the host is not using a
  real-time kernel, expect `communication_constraints_violation` risk.
- Firewall drops can look like robot/control bugs. Check `ufw` before debugging
  libfranka.
- Gravity compensation depends on the Desk end-effector load. A stale load can
  make the arm drift or jump when teaching mode starts.
- Mixed conda/ROS environments can load an old conda `libstdc++`. Use the
  `LD_PRELOAD` workaround above or fix the env package versions before debugging
  `rclpy`.
