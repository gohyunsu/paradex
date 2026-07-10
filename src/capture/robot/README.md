# Robot Capture

Scripts for collecting robot-arm/hand data: teleoperated demonstration
recording and manual waypoint teaching on the XArm.

## Scripts
| File | Purpose |
|------|---------|
| `teleop_real.py` | Record teleoperation sessions on the real robot via XSens/Oculus, optionally with arm and/or hand. Wraps `CaptureSession`. |
| `xarm_teaching.py` | Hand-guide ("manual mode") the XArm and save waypoint poses on a keypress — for building teaching trajectories. |
| `franka_teaching.py` | Use Franka ROS 2 gravity compensation to hand-guide the FR3 and save 7-DoF hand-eye poses. |
| `franka_replay_check.py` | Replay saved Franka hand-eye poses without cameras; use this before full hand-eye capture. |
| `franka_home.py` | Move the FR3 to the default ready pose through `fr3_arm_controller`. |

## Usage

### Teleoperation recording (`teleop_real.py`)
Runs on the **robot/main PC** connected to the teleop device and robot.
```bash
python src/capture/robot/teleop_real.py --device {xsens|occulus} \
    --arm <arm_name> --hand <hand_name> --save_path <dataset_root>
```
Flow per session (driven by teleop device gestures, with audio cues via `chime`):
1. Pre-record teleop loop — move the robot freely to get ready.
2. Gesture transitions out of the loop (`stop` → begin recording; `exit` → quit).
3. Recording starts to `<save_path>/<timestamp>`; another gesture stops it.
Repeats until an `exit` gesture. `--arm`/`--hand` may be omitted to record only
the available devices. Camera is disabled (`camera=False`).

### XArm waypoint teaching (`xarm_teaching.py`)
Runs on the **PC connected to the XArm**. Puts the arm in manual (gravity-comp)
mode so you physically move it.
```bash
python src/capture/robot/xarm_teaching.py --save_path <dir>
```
Keys: `c` = save current pose, `q` = quit. Each `c` writes the joint angles and
the wrist transform for the current arm pose.

### Franka waypoint teaching and replay
Runs on the **main PC with ROS 2 Humble and `~/franka_ros2_ws` sourced**. The robot
must be in Execution mode with FCI active.
```bash
python src/capture/robot/franka_teaching.py
python src/capture/robot/franka_replay_check.py --step --home
python src/capture/robot/franka_home.py
```
`franka_teaching.py` writes poses to `system/current/hecalib/franka/`, which
`src/calibration/handeye/capture.py --arm franka` later replays.

## Inputs & Outputs
- `teleop_real.py`: reads teleop device + robot state; `CaptureSession` writes
  arm/hand/state recordings under `<save_path>/<timestamp>/`.
- `xarm_teaching.py`: reads XArm at `network_info["xarm"]["param"]["ip"]`; writes
  to `--save_path`:
  - `<idx>_qpos.npy` — 6-DOF joint angles (radians).
  - `<idx>_aa.npy` — 4x4 wrist pose matrix (from axis-angle position via `aa2mtx`).
- `franka_teaching.py`: reads `/joint_states` by joint name and TF
  `fr3_link0 -> fr3_link8`; writes:
  - `<idx>_qpos.npy` — 7-DOF FR3 joint angles (radians).
  - `<idx>_aa.npy` — 4x4 flange pose matrix.

## Related
- [`paradex/dataset_acqusition/capture.py`](../../../paradex/dataset_acqusition/capture.py) — `CaptureSession` (`teleop()`, `start()`, `stop()`, `end()`).
- [`paradex/io/robot_controller`](../../../paradex/io/robot_controller) — arm/hand drivers.
- [`paradex/io/teleop`](../../../paradex/io/teleop) — XSens/Oculus input.
- [`paradex/transforms/conversion.py`](../../../paradex/transforms/conversion.py) — `aa2mtx`.
- Sibling: camera capture in [`../camera`](../camera).
