# src/validate — System Validation Harnesses

Standalone scripts that exercise individual subsystems of the distributed Paradex
rig (cameras, signal generator, robot, teleop, networking) to confirm they work
end-to-end before a real capture session. These are diagnostic/smoke-test tools,
not part of the production capture pipeline.

## Recommended Order

Run the cheapest checks first. Move to hardware-triggered or robot-motion checks
only after transport and camera daemons look healthy.

| Stage | Goal | Typical scripts |
|-------|------|-----------------|
| Offline | Catch import/protocol regressions without moving hardware. | `camera_system/hang_recovery_mock.py`, `camera_system/rcc_protocol_mock.py`, `visualizer/franka.py` |
| Main PC ↔ capture PCs | Confirm SSH launch, command delivery, and telemetry return. | `data_sender/main.py`, `command_sender/stream_remote.py` |
| Camera daemons | Confirm each capture PC sees the expected cameras and frame IDs advance. | `camera_system/remote_camera_controller.py --duration 5 --fps 10 --no_stream` |
| Live preview | Confirm the shared-memory stream path and operator visibility. | `src/capture/camera/stream_remote.py` or the browser live monitor |
| Trigger / sync | Confirm hardware trigger timing and multi-camera frame alignment. | `camera_system/signal_generator.py`, `camera_system/sync_check.py --view`, `camera_system/timestamp.py` |
| Calibration quality | Check whether existing calibration still matches the rig. | `calibration/extrinsic_drift.py`, `calibration/compare_xarm_kinematic_calib.py` |
| Robot / hand | Validate real robot motion only in a cleared workspace. | `robot/*`, `robot_controller/*` |

## Subsystems

| Directory | What it validates |
|-----------|-------------------|
| [`calibration/`](calibration/) | Re-evaluates hand-eye / kinematic calibration quality and camera pose drift across sessions |
| [`camera_system/`](camera_system/) | Flir/PySpin camera control, multi-cam loader, frame readers, hardware sync (UTGE900 signal generator + timestamp monitor) |
| [`command_sender/`](command_sender/) | TCP command + data round-trip between main PC and capture PCs |
| [`data_sender/`](data_sender/) | Pub/sub data collection from capture PCs to the main PC |
| `robot/` | Robot arm motion / FK (covered in a separate doc pass) |
| `robot_controller/` | Arm + hand controller plumbing (separate doc pass) |
| `teleop/` | XSens teleop input (separate doc pass) |
| `upload_raw_video/` | Raw video upload path (separate doc pass) |
| `visualizer/` | Viser / Open3D viewer harnesses (separate doc pass) |

> This README covers the camera/network/calibration group. The robot-side
> subsystems (`robot/`, `robot_controller/`, `teleop/`, `upload_raw_video/`,
> `visualizer/`) are documented in a separate pass.

## Distributed-System Shape

Most camera/network validators come in a **main-PC / capture-PC pair**: a `*_remote`
or `main`/`stream_remote` script runs on the main PC and SSHes a `*_client`/`client`
script onto the capture PCs (via `paradex.io.capture_pc.ssh.run_script`). Run the
main-PC script; it launches the capture-PC side for you.

Capture-PC clients normally use the shared command/data ports. Do not run two
validators that both use `DataPublisher` / `DataCollector` or `CommandSender` at
the same time unless the scripts explicitly use separate ports.

## Pass/Fail Reading

- A validation script passing means the tested layer worked in that run. It does
  not prove the whole capture pipeline is ready.
- Camera frame IDs advancing proves acquisition is alive, but not necessarily
  hardware synchronized. Use sync checks for timing.
- Transport latency reported by `DataCollector.get_stats()` measures message age
  between capture PC and main PC. Browser/display latency is a separate layer.
- Hardware-trigger scripts can affect the rig. Confirm the correct signal
  generator device before running them.

## Related
- [`paradex/io/camera_system/`](../../paradex/io/camera_system) — the real camera stack these mirror
- [`paradex/io/capture_pc/`](../../paradex/io/capture_pc) — SSH, command_sender, data_sender
- [`paradex/calibration/`](../../paradex/calibration) — hand-eye solver, calib utils
