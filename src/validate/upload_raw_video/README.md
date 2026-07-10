# Raw Video Processing / Upload Validation

Validates the raw-video pipeline: undistorting captured `.avi` videos and uploading (rsync) the results to the NAS / shared storage.

## Scripts
| File | Purpose |
|------|---------|
| `upload_local.py` | Runs the full `RawVideoProcessor` pipeline (process all raw videos, then wait and monitor progress) — the real entry point. |
| `test_func.py` | Standalone test of the per-video worker `undistort_raw_video()`: undistorts one `.avi`, writes it locally, and rsyncs to the shared NAS path while reporting progress. |

## Usage
```bash
# Full pipeline (processes all raw videos found by RawVideoProcessor)
python src/validate/upload_raw_video/upload_local.py

# Single-file worker test. Use a copied validation clip unless deleting the input is intended.
python src/validate/upload_raw_video/test_func.py /path/to/raw/videos/<serial>.avi
```

No robot/camera hardware required. Requires:
- Captured raw videos on disk under a capture path (e.g. `.../raw/videos/<serial>.avi`).
- Camera intrinsics loadable via `load_camparam` for the matching serial.
- `rsync` available and the shared/NAS path mounted/reachable.

`test_func.py` takes the input path as a CLI argument. The underlying worker deletes
the input file after successful upload, so use a copied validation clip unless
deleting the original raw video is intended.

## What it validates
- A raw video is read, every frame is undistorted (`apply_undistort_map`) with the per-camera map, and re-encoded (MJPG) to `<root>/videos/<serial>.avi`.
- Progress updates print per 30 frames (frame count, fps, ETA).
- The output is rsynced to the shared NAS path; a passing run ends with `status: completed` / "success".

## Related
- [`paradex/video/raw_video_processor.py`](../../../paradex/video/raw_video_processor.py) — `RawVideoProcessor` (`process`, `wait_and_monitor`).
- [`paradex/image/undistort.py`](../../../paradex/image/undistort.py) — `precomute_undistort_map`, `apply_undistort_map`.
- [`paradex/calibration/utils.py`](../../../paradex/calibration/utils.py) — `load_camparam`.
- [`paradex/utils/upload_file.py`](../../../paradex/utils/upload_file.py) — `rsync_copy`.
- [`paradex/utils/path.py`](../../../paradex/utils/path.py) — `capture_path_list`, `shared_dir`, `home_path`.
