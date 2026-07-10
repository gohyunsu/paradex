import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from paradex.io.camera_system.remote_camera_controller import remote_camera_controller


def _all_frame_ids_positive(rcc):
    status = rcc.get_status()
    pc_status = status.get("pc", {})
    for pc in rcc.pc_list:
        info = pc_status.get(pc, {})
        frame_ids = info.get("frame_ids", {}) or {}
        if not frame_ids or any(fid <= 0 for fid in frame_ids.values()):
            return False, status
    return True, status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Main-PC smoke test for capture-PC camera daemons."
    )
    parser.add_argument("--duration", type=float, default=10.0,
                        help="Seconds to wait for every camera frame_id to advance.")
    parser.add_argument("--fps", type=int, default=10,
                        help="Free-run camera FPS when --sync is not set.")
    parser.add_argument("--sync", action="store_true",
                        help="Use hardware trigger sync mode instead of free-run.")
    parser.add_argument("--record", type=str, default=None,
                        help="Optional save path for a short video-sink test.")
    parser.add_argument("--no_stream", action="store_true",
                        help="Do not enable the shared-memory stream sink.")
    args = parser.parse_args()

    rcc = remote_camera_controller("camera_validation")
    try:
        time.sleep(1.0)
        rcc.arm(syncMode=args.sync, fps=args.fps)
        if not args.no_stream:
            rcc.set_stream(True)
        if args.record:
            rcc.set_record(args.record, on=True)

        ok = False
        status = {}
        deadline = time.time() + args.duration
        while time.time() < deadline:
            ok, status = _all_frame_ids_positive(rcc)
            if ok:
                break
            time.sleep(0.3)

        status = status or rcc.get_status()
        print(f"error: {status.get('error')}")
        print(f"stalled: {status.get('stalled')}")
        print(f"capture_interrupted: {status.get('capture_interrupted')}")
        for pc in sorted(rcc.pc_list):
            info = status.get("pc", {}).get(pc, {})
            print(pc)
            print(f"  status: {info.get('status')} {info.get('msg')}")
            print("  expected/detected: "
                  f"{info.get('expected_camera_count')} / "
                  f"{info.get('detected_camera_count')}")
            print(f"  states: {info.get('states')}")
            print(f"  frame_ids: {info.get('frame_ids')}")
            print(f"  errors: {info.get('errors')}")

        if status.get("error") or status.get("capture_interrupted") or not ok:
            raise SystemExit("FAIL: not every camera produced a positive frame_id")
        print("PASS: all capture-PC camera daemons produced positive frame_ids")
    finally:
        try:
            if args.record:
                rcc.set_record(on=False)
            if not args.no_stream:
                rcc.set_stream(False)
            rcc.stop()
        finally:
            rcc.end()
