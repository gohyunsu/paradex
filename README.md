# Paradex

Paradex is a distributed **multi-camera vision + robot-control framework** for
dexterous manipulation research. It coordinates capture PCs, FLIR cameras,
hardware triggers, robot/hand controllers, calibration, dataset capture,
post-processing, and inference scripts.

🌐 **Project page:** open [`index.html`](index.html) (deployable via GitHub Pages).
📚 **Guide + API reference:** [`docs/index.html`](docs/index.html).

---

## Read This First

Use the docs in this order when you are new to the repo:

1. **System map** — understand which code runs on the main PC, capture PCs, and
   robot/control machines.
2. **Configuration** — confirm `system/current/`, camera serials, network IPs,
   shared storage, and hardware trigger settings.
3. **Validation** — run small checks before a real capture session.
4. **Calibration** — run `intrinsic → extrinsic → hand-eye` when the camera rig
   or robot geometry changes.
5. **Capture / process / inference** — collect data, synchronize and undistort it,
   then run downstream pose or grasp pipelines.

```text
configure rig
  -> validate hardware + transport
    -> calibrate cameras and camera-to-robot transform
      -> capture dataset
        -> process synced/undistorted data
          -> run object pose / grasp inference
```

## Repository Map

```
paradex/
├── paradex/   # Core library (general-purpose, reusable modules)
├── src/       # Applications (combine paradex modules for specific tasks)
├── system/    # System configs (camera, network, PC info) — active config in system/current/
├── rsc/       # Resources (robot URDFs, object meshes, hand models)
└── docs/      # Generated Sphinx API reference
```

- **`paradex/`** — calibration, camera IO, robot control, transforms, simulation, retargeting, visualization. Install with `pip install -e .`
- **`src/`** — concrete workflows: calibrate → capture → process → infer. **Every app group has a `README.md` (humans) + `CLAUDE.md` (Claude).** See the [application index](src/README.md).

> **Distributed system:** 6 capture PCs + 1 main PC. Many scripts pair a **Capture-PC** daemon/client (waits for commands) with a **Main-PC** orchestrator (`_remote` / `_main`, sends commands over SSH/TCP). Hardware sync via a UTGE900 signal generator.

---

## Installation

```bash
git clone https://github.com/willi19/paradex.git
cd paradex
pip install -e .
```

System configuration lives under [`system/`](system/) — the active profile is the
`system/current/` symlink (for example `paradex1`, `paradex2`, or a lab-specific
profile).

---

## Quick Start For A Real Rig

### 0. Confirm configuration and daemons

Before camera work, check that:

- `system/current/pc.json` names the main PC and capture PCs correctly.
- `system/current/camera.json` contains the expected camera serials.
- `system/current/network.json` points at the correct command/data ports.
- `~/shared_data` is mounted where capture and processing scripts expect it.

For distributed capture, start the camera daemon on every capture PC:

```bash
python src/camera/server_daemon.py
```

Then use validation scripts from the main PC before a long capture session:

```bash
python src/validate/data_sender/main.py
python src/validate/camera_system/remote_camera_controller.py --duration 5 --fps 10 --no_stream
```

More checks: [`src/validate/`](src/validate/README.md).

### 1. Calibration — run in order: `intrinsic → extrinsic → handeye`

| Step | Command | Notes |
|------|---------|-------|
| Intrinsic | `python src/calibration/intrinsic/capture.py` → `calculate.py` | Per-camera lens calibration. Redo when aperture/focal length/focus changes. |
| Extrinsic | `python src/calibration/extrinsic/capture.py` → `calculate.py` | Charuco + COLMAP. Press `c` to capture, `q` to quit. |
| Hand-eye | `python src/calibration/handeye/capture.py --arm xarm` → `calculate.py --arm xarm` | Camera→robot (`C2R.npy`). Needs extrinsic first. |

Re-run rules: aperture/focal length changed → redo from intrinsic; extrinsic changed → redo hand-eye.
Details: [`src/calibration/`](src/calibration/README.md).

### 2. Capture

```bash
# on the main PC
python src/capture/camera/image_remote.py --save_path dataset/001
python src/capture/camera/video_remote.py --save_path dataset/001 --sync_mode
```

Details: [`src/capture/`](src/capture/README.md) · [`src/camera/`](src/camera/README.md).

### 3. Process and infer

- Build datasets: [`src/dataset_acquisition/`](src/dataset_acquisition/README.md)
- Post-process (sync, undistort, COLMAP): [`src/process/`](src/process/README.md)
- 6D pose & grasp: [`src/object6d/`](src/object6d/README.md) · [`src/inference/`](src/inference/README.md)

---

## Where To Go Next

| Need | Start here |
|------|------------|
| Understand the system architecture | [`docs/index.html`](docs/index.html), then [`docs/camera_system.md`](docs/camera_system.md) |
| Find runnable application scripts | [`src/README.md`](src/README.md) |
| Validate cameras, transport, sync, or robot plumbing | [`docs/validation.md`](docs/validation.md), [`src/validate/README.md`](src/validate/README.md) |
| Run calibration | [`src/calibration/README.md`](src/calibration/README.md), [`docs/calibration.md`](docs/calibration.md) |
| Capture data | [`src/capture/README.md`](src/capture/README.md), [`docs/capture.md`](docs/capture.md) |
| Process captured data | [`src/process/README.md`](src/process/README.md), [`docs/process.md`](docs/process.md) |
| Work as an AI coding agent | [`agent_docs/README.md`](agent_docs/README.md), [`CLAUDE.md`](CLAUDE.md) |

Full application index: [`src/README.md`](src/README.md).

---

## Documentation

- **Human guide and API reference:** [`docs/index.html`](docs/index.html)
- **Application READMEs:** [`src/README.md`](src/README.md) and each `src/*/README.md`
- **Agent-oriented subsystem notes:** [`agent_docs/README.md`](agent_docs/README.md)
- **Project landing page:** [`index.html`](index.html) — host with GitHub Pages
  (deploy from branch → root). `.nojekyll` is included so Sphinx `_static` and
  `_modules` directories serve correctly.

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. **`paradex/`** — keep functions general and reusable.
3. **`src/`** — combine paradex modules for specific applications; add/update the app's `README.md` + `CLAUDE.md`.
