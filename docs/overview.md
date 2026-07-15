# System Overview

Paradex is easiest to understand as a staged distributed system:

```text
configure rig
  -> validate hardware + transport
    -> calibrate cameras and camera-to-robot geometry
      -> capture raw synchronized data
        -> process synced and undistorted data
          -> run pose, grasp, or analysis pipelines
```

## Runtime Surfaces

| Surface | Runs where | Typical responsibility |
|---------|------------|------------------------|
| Main PC | operator workstation | Orchestrates capture PCs, starts validation, sends camera/command requests, aggregates data. |
| Capture PCs | camera machines | Own FLIR cameras through long-running daemons and publish previews/status. |
| Robot/control machine | robot-side host or main PC, depending on setup | Runs arm/hand controllers and streams robot state. |
| Shared storage | mounted as `~/shared_data` | Stores calibration, raw captures, processed videos, and results. |

The main PC normally does **not** open camera hardware directly. It sends commands
to capture-PC daemons, which own the FLIR SDK lifecycle.

## Code Layout

| Path | Role |
|------|------|
| `paradex/` | Reusable library modules: camera IO, capture-PC transport, calibration utilities, robot wrappers, transforms, visualization, processing helpers. |
| `src/` | Runnable applications that combine library modules into real workflows. Start at `src/README.md`. |
| `system/` | Rig configuration. `system/current/` selects the active profile. |
| `rsc/` | Robot URDFs, hand models, meshes, and other static resources. |
| `docs/` | Sphinx guide and generated API pages. |
| `agent_docs/` | Task-oriented subsystem notes for AI coding agents. |

## Read Order

1. {doc}`camera_system` — how distributed camera daemons, shared memory, and
   controller heartbeats work.
2. {doc}`calibration` — where intrinsic, extrinsic, and hand-eye parameters live.
3. {doc}`capture` — how a capture session coordinates cameras, robot streams,
   trigger signals, and timestamps.
4. {doc}`dataset_acquisition` — how dataset-specific scripts use capture sessions.
5. {doc}`process` — how raw data is synchronized, undistorted, reconstructed, or uploaded.
6. API pages only after the mental model is clear.

## Practical Bring-Up Order

1. Confirm `system/current/pc.json`, `camera.json`, `network.json`, and shared storage.
2. Start `src/camera/server_daemon.py` on every capture PC.
3. Run transport and camera validation from `src/validate/`.
4. Run calibration in order: intrinsic, extrinsic, hand-eye.
5. Run a short capture and verify output layout before collecting a full dataset.

Use {doc}`camera_system` for camera failures and {doc}`calibration` for geometry
or projection failures.
