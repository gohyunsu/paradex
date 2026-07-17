"""Tight, low-latency multi-camera monitor with synchronization status.

Run on the Main PC:

    python -m src.ui.monitor --fps 30
    python -m src.ui.monitor --trigger --seconds 10

Press ``q`` to close. The display always renders only the newest frame received
for each camera; it never queues old frames behind a slow display refresh.
"""

from __future__ import annotations

import argparse
import math
import signal
import time
from dataclasses import dataclass
from threading import Event
from typing import Dict, Set, Tuple


@dataclass
class Frame:
    image: object
    frame_id: int
    updated_at: float


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paradex multi-camera monitor")
    parser.add_argument("--fps", type=int, default=30, help="capture FPS")
    parser.add_argument("--sync", action="store_true", help="enable hardware-triggered capture")
    parser.add_argument(
        "--trigger",
        action="store_true",
        help="start the configured UTGE900 trigger after cameras are armed",
    )
    parser.add_argument("--seconds", type=float, default=0, help="stop after this duration; 0 runs until q")
    parser.add_argument(
        "--warmup-seconds",
        type=float,
        default=1,
        help="exclude this initial interval from timed validation summaries",
    )
    parser.add_argument("--max-width", type=int, default=1920, help="maximum display width")
    parser.add_argument("--max-height", type=int, default=1080, help="maximum display height")
    parser.add_argument("--tile-width", type=int, default=384, help="unscaled tile width")
    parser.add_argument(
        "--sync-tolerance",
        type=int,
        default=1,
        help="maximum acceptable frame-ID spread; matches sync_check.py",
    )
    parser.add_argument("--stale-ms", type=int, default=1000, help="camera stale threshold")
    return parser


def sync_summary(
    frames: Dict[str, Frame], stale_after: float
) -> Tuple[int, int, int, Set[str], str]:
    """Return median, min/max spread, stale names, and a concise sync state."""
    frame_ids = sorted(frame.frame_id for frame in frames.values() if frame.frame_id > 0)
    if not frame_ids:
        return 0, 0, 0, set(), "WAITING"
    now = time.monotonic()
    stale = {name for name, frame in frames.items() if now - frame.updated_at > stale_after}
    median = frame_ids[len(frame_ids) // 2]
    return median, frame_ids[0], frame_ids[-1], stale, "READY"


def compose(frames, expected, args, cv2, np):
    """Compose aspect-preserving camera tiles with a compact sync status strip."""
    names = sorted(frames)
    sample = frames[names[0]].image
    source_h, source_w = sample.shape[:2]
    tile_w = args.tile_width
    tile_h = max(1, round(tile_w * source_h / source_w))
    cols = max(1, math.ceil(math.sqrt(len(names))))
    rows = math.ceil(len(names) / cols)
    strip_h = 42
    median, low, high, stale, ready = sync_summary(frames, args.stale_ms / 1000)
    spread = high - low

    if ready == "WAITING":
        state, state_color = "WAITING", (90, 180, 255)
    elif stale or spread > args.sync_tolerance:
        state, state_color = "OUT OF SYNC", (45, 45, 230)
    elif spread:
        state, state_color = "SYNC OK / JITTER", (50, 190, 70)
    else:
        state, state_color = "SYNC OK", (50, 190, 70)

    canvas = np.zeros((rows * tile_h + strip_h, cols * tile_w, 3), dtype=np.uint8)
    for index, name in enumerate(names):
        frame = frames[name]
        image = cv2.resize(frame.image, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
        delta = frame.frame_id - median if median else 0
        if name in stale:
            border = (45, 45, 230)
            detail = "STALE"
        elif spread > args.sync_tolerance and frame.frame_id != high:
            border = (45, 45, 230)
            detail = f"LAG d{delta:+d}"
        elif frame.frame_id != high:
            border = (0, 180, 255)
            detail = f"JITTER d{delta:+d}"
        else:
            border = (50, 190, 70)
            detail = f"d{delta:+d}"
        cv2.rectangle(image, (0, 0), (tile_w - 1, tile_h - 1), border, 5)
        label = f"{name}  f{frame.frame_id}  {detail}"
        cv2.rectangle(image, (0, 0), (min(tile_w, 16 + 11 * len(label)), 28), (0, 0, 0), -1)
        cv2.putText(image, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (235, 235, 235), 1, cv2.LINE_AA)
        row, col = divmod(index, cols)
        canvas[row * tile_h:(row + 1) * tile_h, col * tile_w:(col + 1) * tile_w] = image

    message = f"{state}  |  cameras {len(names)}/{expected}  |  frame spread {spread} ({low}-{high})  |  median {median}"
    if stale:
        message += f"  |  stale {len(stale)}"
    cv2.rectangle(canvas, (0, rows * tile_h), (cols * tile_w, rows * tile_h + strip_h), state_color, -1)
    cv2.putText(canvas, message, (12, rows * tile_h + 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 2, cv2.LINE_AA)

    scale = min(args.max_width / canvas.shape[1], args.max_height / canvas.shape[0], 1.0)
    if scale < 1.0:
        canvas = cv2.resize(canvas, (round(canvas.shape[1] * scale), round(canvas.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    return canvas, spread, state


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    if args.trigger:
        args.sync = True
    import cv2
    import numpy as np

    from paradex.io.camera_system.remote_camera_controller import remote_camera_controller
    from paradex.io.camera_system.signal_generator import UTGE900
    from paradex.io.capture_pc.command_sender import CommandSender
    from paradex.io.capture_pc.data_sender import DataCollector
    from paradex.io.capture_pc.ssh import run_script
    from paradex.utils.system import get_camera_list, get_pc_list, network_info

    expected = sum(len(get_camera_list(pc)) for pc in get_pc_list())
    frames: Dict[str, Frame] = {}
    decoded = 0
    last_report = time.monotonic()
    controller = None
    collector = None
    sender = None
    trigger = None
    window = "Paradex / Monitor"
    stopping = Event()
    validation_samples = 0
    worst_spread = 0
    validation_state = "WAITING"
    previous_handlers = {
        signal.SIGINT: signal.getsignal(signal.SIGINT),
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
    }

    def request_stop(_signum, _frame):
        stopping.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        run_script("python src/capture/camera/stream_client.py")
        sender = CommandSender()
        collector = DataCollector()
        collector.start()
        controller = remote_camera_controller("monitor")
        controller.arm(syncMode=args.sync, fps=args.fps)
        if args.trigger:
            trigger = UTGE900(**network_info["signal_generator"]["param"])
            trigger.start(fps=args.fps)
        controller.set_stream(True)
        window_flags = (
            cv2.WINDOW_NORMAL
            | cv2.WINDOW_KEEPRATIO
            | getattr(cv2, "WINDOW_GUI_NORMAL", 0)
        )
        cv2.namedWindow(window, window_flags)
        displayed_size = None
        started_at = time.monotonic()

        while not stopping.is_set():
            for name, item in collector.get_data().items():
                if item.get("type") != "image" or not item.get("data"):
                    continue
                image = cv2.imdecode(np.frombuffer(item["data"], dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    continue
                frame_id = int(item.get("frame_id", 0))
                previous = frames.get(name)
                updated_at = time.monotonic() if previous is None or previous.frame_id != frame_id else previous.updated_at
                frames[name] = Frame(image, frame_id, updated_at)
                decoded += 1

            if frames:
                display, spread, state = compose(frames, expected, args, cv2, np)
                if (
                    args.seconds
                    and len(frames) == expected
                    and time.monotonic() - started_at >= args.warmup_seconds
                ):
                    validation_samples += 1
                    worst_spread = max(worst_spread, spread)
                    validation_state = state
                size = (display.shape[1], display.shape[0])
                if size != displayed_size:
                    cv2.resizeWindow(window, *size)
                    displayed_size = size
                cv2.imshow(window, display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                stopping.set()
            if args.seconds and time.monotonic() - started_at >= args.seconds:
                stopping.set()
            if time.monotonic() - last_report >= 1.0:
                stats = collector.get_stats()
                latencies = [item["latency_ms"] for item in stats.values() if item["recv"]]
                transport = sum(latencies) / len(latencies) if latencies else 0.0
                print(f"cameras={len(frames)}/{expected} sync={state if frames else 'WAITING'} frame_spread={spread if frames else 0} transport={transport:.1f}ms decoded={decoded}/s", flush=True)
                decoded, last_report = 0, time.monotonic()
    finally:
        cv2.destroyAllWindows()
        if controller is not None:
            for action in (controller.stop, controller.end):
                try:
                    action()
                except Exception:
                    pass
        if trigger is not None:
            for action in (trigger.stop, trigger.end):
                try:
                    action()
                except Exception:
                    pass
        if collector is not None:
            collector.end()
        if sender is not None:
            sender.end()
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    if args.seconds:
        passed = validation_samples > 0 and worst_spread <= args.sync_tolerance
        print(
            "SYNC VALIDATION "
            f"{'PASS' if passed else 'FAIL'} | samples={validation_samples} "
            f"worst_spread={worst_spread} tolerance={args.sync_tolerance} "
            f"final_state={validation_state}",
            flush=True,
        )
        return 0 if passed else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
