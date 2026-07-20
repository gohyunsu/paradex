"""Validate per-Capture-PC camera sync using the Main PC's UTG900E trigger."""

import argparse
import time

from paradex.io.camera_system.remote_camera_controller import remote_camera_controller
from paradex.io.camera_system.signal_generator import UTGE900
from paradex.utils.system import network_info


def require_ok(stage, response):
    failed = {pc: item.get("msg", item) for pc, item in response.items() if item.get("status") != "ok"}
    if failed:
        raise RuntimeError(f"{stage} failed: {failed}")


def main():
    parser = argparse.ArgumentParser(description="Check per-Capture-PC hardware trigger synchronization.")
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--tolerance", type=int, default=1)
    parser.add_argument("--force-takeover", action="store_true")
    args = parser.parse_args()

    controller = None
    trigger = None
    samples = {}
    raw_worst = {}
    progress_worst = {}
    baseline = {}
    try:
        controller = remote_camera_controller("remote_sync_check")
        time.sleep(1.0)
        if args.force_takeover:
            require_ok("force takeover", controller.force_takeover())

        controller.arm(syncMode=True, fps=args.fps)
        require_ok("camera arm", controller.last_response)
        trigger = UTGE900(**network_info["signal_generator"]["param"])
        trigger.start(fps=args.fps)

        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            for pc, health in controller.get_status()["pc"].items():
                frame_ids = health.get("frame_ids", {})
                if not frame_ids or any(frame_id <= 0 for frame_id in frame_ids.values()):
                    continue
                if pc not in baseline:
                    baseline[pc] = dict(frame_ids)
                raw_spread = max(frame_ids.values()) - min(frame_ids.values())
                progress = [frame_ids[name] - baseline[pc][name] for name in frame_ids]
                progress_spread = max(progress) - min(progress)
                samples[pc] = samples.get(pc, 0) + 1
                raw_worst[pc] = max(raw_worst.get(pc, 0), raw_spread)
                progress_worst[pc] = max(progress_worst.get(pc, 0), progress_spread)
            time.sleep(0.05)
    finally:
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                pass
            controller.end()
        if trigger is not None:
            try:
                trigger.stop()
            finally:
                trigger.end()

    expected = controller.pc_list if controller is not None else []
    missing = [pc for pc in expected if samples.get(pc, 0) == 0]
    passed = not missing and all(spread <= args.tolerance for spread in progress_worst.values())
    for pc in expected:
        print(
            f"{pc}: samples={samples.get(pc, 0)} "
            f"raw_worst_spread={raw_worst.get(pc, 'n/a')} "
            f"progress_worst_spread={progress_worst.get(pc, 'n/a')}"
        )
    print(
        f"REMOTE SYNC {'PASS' if passed else 'FAIL'} | "
        f"tolerance={args.tolerance} missing={missing}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
