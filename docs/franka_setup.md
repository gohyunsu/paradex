# Franka FR3 Setup Notes

Status checked: 2026-07-10.

This document records the current state of Franka support in the `gohyunsu/paradex`
fork and the recommended path to run the Paradex pipeline with a Franka FR3 arm.

## Current Status

The current `main` line does not yet run a real Franka arm end to end.

What is already present:

- `rsc/robot/franka.urdf`: FR3 arm URDF for FK, visualization, and planning-side work.
- `src/validate/visualizer/franka.py`: URDF/Viser smoke test. This does not move hardware.
- `system/paradex2/network.json` and `system/robothome/network.json`: existing `franka`
  IP entries.
- `paradex/transforms/coordinate.py`: `franka` frame entries.
- `paradex/retargetor/unimanual.py`: accepts `arm_name="franka"` at the retargeting API
  boundary.

What is missing on current `main`:

- `paradex/io/robot_controller/franka_controller.py`.
- `get_arm("franka")` factory support. The branch is currently commented out.
- `src/calibration/handeye/capture.py --arm franka`.
- Franka FK link selection in `src/calibration/handeye/calculate.py`
  (`xarm` uses `link6`; FR3 should use `fr3_link8`).
- A checked-in `system/current/` runtime config. The loader reads
  `system/current/network.json` and `system/current/pc.json` at import time.

There is relevant Franka work on `origin/vlm_dex`, including:

- `paradex/io/robot_controller/franka_controller.py`
- `src/capture/robot/franka_teaching.py`
- `src/capture/robot/franka_replay_check.py`
- `src/capture/robot/franka_home.py`
- `docs/franka_handeye.md`
- `rsc/robot/fr3_inspire/`

Do not merge the full `origin/vlm_dex` branch into current `main` without review.
It diverges broadly from the current camera/process/site structure. Port only the
Franka-specific pieces.

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
```

## Paradex Config

Create or link `system/current/` for the machine that will run the pipeline. The
current loader imports:

```text
system/current/network.json
system/current/pc.json
system/current/camera.json
system/current/charuco_info.json
```

For Franka, the current main config format should be normalized before controller
factory support is enabled. Prefer the xArm-style structure:

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

If the controller uses ROS 2 only and does not need `robot_ip` directly, keep the
entry anyway so scripts can identify the arm consistently.

## Porting Plan

Recommended minimal port from `origin/vlm_dex`:

1. Add `paradex/io/robot_controller/franka_controller.py`.
2. Enable `get_arm("franka")` in `paradex/io/robot_controller/__init__.py`.
3. Add the Franka utility scripts:
   - `src/capture/robot/franka_home.py`
   - `src/capture/robot/franka_teaching.py`
   - `src/capture/robot/franka_replay_check.py`
4. Update hand-eye capture:
   - `src/calibration/handeye/capture.py --arm franka`
   - instantiate `FrankaController`
   - record `eef.npy` as `fr3_link0 -> fr3_link8`
5. Update hand-eye solve:
   - use `EEF_LINK = {"xarm": "link6", "franka": "fr3_link8"}`
   - compute FK from `rsc/robot/franka.urdf`
6. Add validation scripts before running full capture:
   - controller construction
   - current qpos/state readback
   - home move
   - replay of taught poses without cameras
7. Only after those pass, run `src/calibration/handeye/capture.py --arm franka`.

## Pipeline Order

After porting, the Franka path should be:

1. Start camera daemons on capture PCs.
2. Start the Franka ROS 2 stack on the main PC.
3. Teach hand-eye poses:

```bash
python src/capture/robot/franka_teaching.py
```

4. Replay motion without cameras:

```bash
python src/capture/robot/franka_replay_check.py --step --home
```

5. Capture multi-camera hand-eye data:

```bash
python src/calibration/handeye/capture.py --arm franka
```

6. Solve without ROS in `PYTHONPATH` if ROS Pinocchio conflicts with the conda
   Pinocchio/Numpy stack:

```bash
PYTHONPATH= python src/calibration/handeye/calculate.py --arm franka
```

7. Validate C2R with robot overlays before collecting task data.

## Known Risks

- Full `origin/vlm_dex` merge is high risk because it changes many unrelated
  files and predates the current `paradex.process` and camera transport cleanup.
- `DEVICE2WRIST["franka"]` is currently documented as non-orthonormal. Fix or
  validate it before relying on retargeted teleop actions.
- Franka FCI requires stable 1 kHz control timing. If the host is not using a
  real-time kernel, expect `communication_constraints_violation` risk.
- Firewall drops can look like robot/control bugs. Check `ufw` before debugging
  libfranka.
- Gravity compensation depends on the Desk end-effector load. A stale load can
  make the arm drift or jump when teaching mode starts.
