# Validation

Validation scripts are small, targeted checks that answer: "is this subsystem
ready enough for a real capture run?" They are not replacements for a full
dataset trial, but they narrow failures before you involve cameras, triggers, or
robots.

## Order Of Operations

```text
offline mocks
  -> main/capture PC transport
    -> camera daemon frame IDs
      -> live preview
        -> hardware trigger and sync
          -> calibration quality
            -> robot / hand motion
```

| Level | Use when | What passing means |
|-------|----------|--------------------|
| Offline | You just pulled code or changed protocol logic. | Imports, timeout behavior, and mocked controller contracts are sane. |
| Transport | Before camera streaming or distributed capture. | SSH launch, command delivery, and telemetry return across capture PCs work. |
| Camera daemon | Before recording. | Daemons can arm cameras and frame IDs advance on every expected camera. |
| Live preview | Before operator-facing capture. | Shared-memory camera frames reach the main PC and display path. |
| Sync | Before synced datasets. | Triggered cameras stay within frame-ID tolerance. |
| Calibration quality | Before geometry-dependent inference. | Existing cam params and camera-to-robot transform are still plausible. |
| Robot / hand | Before motion tasks. | Controllers can move and report state; run only with a cleared workspace. |

## Common Commands

```bash
# Offline / no robot motion
python src/validate/camera_system/hang_recovery_mock.py
python src/validate/camera_system/rcc_protocol_mock.py

# Main PC to capture PC transport
python src/validate/data_sender/main.py
python src/validate/command_sender/stream_remote.py

# Camera daemon frame IDs
python src/validate/camera_system/remote_camera_controller.py --duration 5 --fps 10 --no_stream

# Trigger and sync checks
python src/validate/camera_system/sync_check.py --view
python src/validate/camera_system/timestamp.py

# Calibration quality checks
python src/validate/calibration/extrinsic_drift.py
python src/validate/calibration/compare_xarm_kinematic_calib.py --no_overlay
```

## Reading Results

- Positive frame IDs mean cameras are producing frames. They do **not** prove
  cameras are synchronized.
- `DataCollector.get_stats()` latency is transport latency, not display latency.
  Browser previews can add their own decode/render delay.
- Hardware trigger checks should be run only after confirming the signal generator
  path in `system/current`.
- Robot checks should be treated as real motion tests, not smoke tests.

For script-by-script ownership and notes, see `src/validate/README.md`.
