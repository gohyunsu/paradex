#!/usr/bin/env python3
"""Browser monitor for the distributed Paradex camera preview stream.

Run this on the main PC. The browser Start button launches the existing
capture-PC stream clients, arms camera acquisition through
``remote_camera_controller``, and displays the merged JPEG preview.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import ModuleType
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_cv_stack() -> tuple[ModuleType, ModuleType, Any]:
    try:
        import cv2
        import numpy as np
        from paradex.image.merge import merge_image
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV and NumPy are required. Activate the Paradex/FLIR conda "
            "environment before running live_monitor.py."
        ) from exc
    return cv2, np, merge_image


def load_runtime_stack() -> tuple[Any, Any, Any, Any]:
    from paradex.io.camera_system.remote_camera_controller import remote_camera_controller
    from paradex.io.capture_pc.command_sender import CommandSender
    from paradex.io.capture_pc.data_sender import DataCollector
    from paradex.io.capture_pc.ssh import run_script

    return remote_camera_controller, CommandSender, DataCollector, run_script


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Paradex Camera Monitor</title>
  <style>
    :root {
      --ink: #202225;
      --muted: #66717a;
      --paper: #ffffff;
      --soft: #f4f7f8;
      --line: #d9e2e7;
      --teal: #007c89;
      --teal-dark: #07545e;
      --green: #2f7d4f;
      --red: #b84d3b;
      --amber: #9d6508;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--soft);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    button, input { font: inherit; }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.9rem 1rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.7rem;
      min-width: 0;
      font-weight: 780;
    }
    .mark {
      display: grid;
      place-items: center;
      width: 2rem;
      height: 2rem;
      border-radius: 50%;
      color: #fff;
      background: var(--teal);
      flex: 0 0 auto;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
      justify-content: flex-end;
    }
    .btn {
      min-height: 2.4rem;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--paper);
      color: var(--ink);
      padding: 0.45rem 0.8rem;
      font-weight: 720;
      cursor: pointer;
    }
    .btn.primary {
      color: #fff;
      background: var(--teal);
      border-color: var(--teal);
    }
    .btn.danger {
      color: #fff;
      background: var(--red);
      border-color: var(--red);
    }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    main {
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 1rem;
      padding: 1rem;
    }
    .viewer {
      min-width: 0;
      min-height: 420px;
      height: min(72vh, 780px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: #101820;
      overflow: hidden;
      display: grid;
      place-items: center;
    }
    .viewer img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #101820;
    }
    aside {
      min-width: 0;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      align-content: start;
      gap: 1rem;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--paper);
      padding: 1rem;
    }
    .panel h2 {
      margin: 0 0 0.8rem;
      font-size: 1rem;
      letter-spacing: 0;
    }
    .panel-status,
    .panel-frames {
      grid-column: span 2;
    }
    .status-line {
      display: grid;
      grid-template-columns: 7rem minmax(0, 1fr);
      gap: 0.5rem;
      padding: 0.42rem 0;
      border-top: 1px solid var(--line);
      font-size: 0.92rem;
    }
    .status-line:first-of-type { border-top: 0; }
    .label {
      color: var(--muted);
      font-weight: 720;
    }
    .value {
      min-width: 0;
      overflow-wrap: anywhere;
      font-variant-numeric: tabular-nums;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      min-height: 1.75rem;
      border-radius: 999px;
      padding: 0.16rem 0.55rem;
      color: var(--teal-dark);
      background: #e8f4f5;
      font-size: 0.84rem;
      font-weight: 780;
    }
    .chip.running {
      color: #fff;
      background: var(--green);
    }
    .chip.error {
      color: #fff;
      background: var(--red);
    }
    .chip.starting {
      color: #fff;
      background: var(--amber);
    }
    .list {
      display: grid;
      gap: 0.55rem;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0.65rem;
      background: #fbfcfd;
    }
    .item strong,
    .item span {
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .item span {
      color: var(--muted);
      font-size: 0.86rem;
      margin-top: 0.12rem;
    }
    .error-text {
      color: var(--red);
      font-weight: 680;
    }
    code {
      background: #eef3f5;
      border-radius: 5px;
      padding: 0.08rem 0.3rem;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 0.9em;
    }
    @media (max-width: 980px) {
      aside {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .viewer img {
        min-height: 0;
      }
    }
    @media (max-width: 620px) {
      header {
        align-items: flex-start;
        flex-direction: column;
      }
      .actions,
      .btn {
        width: 100%;
      }
      .status-line {
        grid-template-columns: 1fr;
      }
      aside,
      .panel-status,
      .panel-frames {
        grid-template-columns: 1fr;
        grid-column: auto;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="brand"><span class="mark">P</span><span>Paradex Camera Monitor</span></div>
      <div class="actions">
        <button id="start" class="btn primary" type="button">Start stream</button>
        <button id="stop" class="btn danger" type="button">Stop</button>
        <button id="refresh" class="btn" type="button">Refresh</button>
      </div>
    </header>

    <main>
      <section class="viewer" aria-label="Live merged camera preview">
        <img id="feed" src="/stream.mjpg" alt="Merged live camera preview" />
      </section>

      <aside>
        <section class="panel panel-status" aria-labelledby="status-title">
          <h2 id="status-title">Status</h2>
          <div class="status-line">
            <span class="label">State</span>
            <span class="value"><span id="state" class="chip">Idle</span></span>
          </div>
          <div class="status-line">
            <span class="label">Cameras</span>
            <span id="camera-count" class="value">0</span>
          </div>
          <div class="status-line">
            <span class="label">Last frame</span>
            <span id="last-frame" class="value">none</span>
          </div>
          <div class="status-line">
            <span class="label">FPS</span>
            <span id="fps" class="value">-</span>
          </div>
          <div class="status-line">
            <span class="label">Error</span>
            <span id="error" class="value">none</span>
          </div>
        </section>

        <section class="panel panel-pcs" aria-labelledby="pcs-title">
          <h2 id="pcs-title">Capture PCs</h2>
          <ul id="pcs" class="list"></ul>
        </section>

        <section class="panel panel-frames" aria-labelledby="frames-title">
          <h2 id="frames-title">Frames</h2>
          <ul id="frames" class="list"></ul>
        </section>

        <section class="panel panel-run" aria-labelledby="run-title">
          <h2 id="run-title">Run</h2>
          <div class="status-line">
            <span class="label">Daemons</span>
            <span class="value"><code>src/camera/server_daemon.py</code></span>
          </div>
          <div class="status-line">
            <span class="label">Client</span>
            <span class="value"><code>src/capture/camera/stream_client.py</code></span>
          </div>
          <div class="status-line">
            <span class="label">Preview</span>
            <span class="value">1/8 JPEG stream</span>
          </div>
        </section>
      </aside>
    </main>
  </div>

  <script>
    const els = {
      start: document.getElementById("start"),
      stop: document.getElementById("stop"),
      refresh: document.getElementById("refresh"),
      state: document.getElementById("state"),
      cameraCount: document.getElementById("camera-count"),
      lastFrame: document.getElementById("last-frame"),
      fps: document.getElementById("fps"),
      error: document.getElementById("error"),
      pcs: document.getElementById("pcs"),
      frames: document.getElementById("frames"),
      feed: document.getElementById("feed")
    };

    let busy = false;

    function ageText(seconds) {
      if (seconds === null || seconds === undefined) return "none";
      if (seconds < 1) return `${Math.round(seconds * 1000)} ms ago`;
      return `${seconds.toFixed(1)} s ago`;
    }

    function item(title, detail) {
      const li = document.createElement("li");
      li.className = "item";
      const strong = document.createElement("strong");
      const span = document.createElement("span");
      strong.textContent = title;
      span.textContent = detail;
      li.append(strong, span);
      return li;
    }

    function setList(node, rows, emptyText) {
      node.replaceChildren();
      if (!rows.length) {
        node.append(item(emptyText, ""));
        return;
      }
      rows.forEach(row => node.append(row));
    }

    function renderStatus(data) {
      const hasError = Boolean(data.error || data.rcc?.error);
      els.state.className = "chip";
      if (hasError) {
        els.state.classList.add("error");
        els.state.textContent = "Error";
      } else if (data.starting) {
        els.state.classList.add("starting");
        els.state.textContent = "Starting";
      } else if (data.running) {
        els.state.classList.add("running");
        els.state.textContent = "Streaming";
      } else {
        els.state.textContent = "Idle";
      }

      els.cameraCount.textContent = String(data.camera_count || 0);
      els.lastFrame.textContent = ageText(data.last_frame_age_sec);
      els.fps.textContent = data.config ? `${data.config.camera_fps} camera / ${data.config.ui_fps} UI` : "-";
      els.error.textContent = data.error || data.rcc?.interrupt_msg || "none";
      els.error.className = data.error ? "value error-text" : "value";

      const pcRows = Object.entries(data.rcc?.pc || {}).map(([pc, status]) => {
        const state = status.status || "unknown";
        const msg = status.msg || `detected ${status.detected_camera_count ?? "-"} / expected ${status.expected_camera_count ?? "-"}`;
        return item(pc, `${state}: ${msg}`);
      });
      setList(els.pcs, pcRows, "No daemon status");

      const frameRows = Object.entries(data.frames || {}).map(([name, frame]) => {
        const age = frame.receive_age_ms === null ? "-" : `${Math.round(frame.receive_age_ms)} ms`;
        return item(name, `fid ${frame.frame_id} · ${frame.pc || "pc?"} · seq ${frame.seq ?? "-"} · shown age ${age}`);
      });
      setList(els.frames, frameRows, "No frames yet");

      els.start.disabled = busy || data.running || data.starting;
      els.stop.disabled = busy || (!data.running && !data.starting);
    }

    async function refresh() {
      try {
        const res = await fetch("/api/status", {cache: "no-store"});
        renderStatus(await res.json());
      } catch (err) {
        renderStatus({error: String(err), running: false, starting: false});
      }
    }

    async function post(path) {
      busy = true;
      await refresh();
      try {
        const res = await fetch(path, {method: "POST"});
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || res.statusText);
        if (path.endsWith("/start")) {
          els.feed.src = `/stream.mjpg?t=${Date.now()}`;
        }
        renderStatus(data);
      } catch (err) {
        renderStatus({error: String(err), running: false, starting: false});
      } finally {
        busy = false;
        await refresh();
      }
    }

    els.start.addEventListener("click", () => post("/api/start"));
    els.stop.addEventListener("click", () => post("/api/stop"));
    els.refresh.addEventListener("click", refresh);
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class CameraMonitor:
    def __init__(
        self,
        *,
        pc_list: list[str] | None,
        camera_fps: int,
        ui_fps: int,
        jpeg_quality: int,
        launch_clients: bool,
        client_command: str,
        remote_log: bool,
        command_timeout_ms: int,
        command_retries: int,
    ) -> None:
        self.pc_list = pc_list
        self.camera_fps = camera_fps
        self.ui_fps = max(1, ui_fps)
        self.jpeg_quality = max(1, min(100, int(jpeg_quality)))
        self.launch_clients = launch_clients
        self.client_command = client_command
        self.remote_log = remote_log
        self.command_timeout_ms = command_timeout_ms
        self.command_retries = command_retries
        self.cv2, self.np, self.merge_image = load_cv_stack()

        self.lifecycle_lock = threading.RLock()
        self.frame_cond = threading.Condition()
        self.collect_stop = threading.Event()

        self.rcc: Any | None = None
        self.dc: Any | None = None
        self.cs: Any | None = None
        self.collect_thread: threading.Thread | None = None

        self.running = False
        self.starting = False
        self.error: str | None = None
        self.latest_jpeg: bytes | None = None
        self.latest_version = 0
        self.last_frame_time: float | None = None
        self.frames: dict[str, dict[str, Any]] = {}
        self.frame_seen_at: dict[str, float] = {}
        self.frame_versions: dict[str, tuple[int | None, int | None]] = {}
        self.placeholder_jpeg = self._make_placeholder("Click Start stream")

    def start(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            if self.running or self.starting:
                return self.status()
            self.starting = True
            self.error = None

        try:
            remote_camera_controller, CommandSender, DataCollector, run_script = load_runtime_stack()
            if self.launch_clients:
                run_script(self.client_command, pc_list=self.pc_list, log=self.remote_log)

            rcc = remote_camera_controller("camera_live_monitor", pc_list=self.pc_list)
            dc = DataCollector(pc_list=self.pc_list)
            dc.start()
            cs = CommandSender(
                pc_list=self.pc_list,
                timeout=self.command_timeout_ms,
                retries=self.command_retries,
            )

            rcc.arm(syncMode=False, fps=self.camera_fps)
            rcc.set_stream(True)

            with self.lifecycle_lock:
                self.rcc = rcc
                self.dc = dc
                self.cs = cs
                self.collect_stop.clear()
                self.running = True
                self.starting = False
                self.latest_jpeg = None
                self.latest_version = 0
                self.last_frame_time = None
                self.frames = {}
                self.frame_seen_at = {}
                self.frame_versions = {}
                self.collect_thread = threading.Thread(
                    target=self._collect_loop,
                    name="camera-live-monitor-collector",
                    daemon=True,
                )
                self.collect_thread.start()
            return self.status()
        except Exception as exc:
            with self.lifecycle_lock:
                self.error = str(exc)
                self.starting = False
            self._cleanup_handles(locals().get("rcc"), locals().get("dc"), locals().get("cs"))
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            rcc, dc, cs = self.rcc, self.dc, self.cs
            thread = self.collect_thread
            self.running = False
            self.starting = False
            self.rcc = None
            self.dc = None
            self.cs = None
            self.collect_thread = None
            self.collect_stop.set()

        if thread is not None:
            thread.join(timeout=2)
        self._cleanup_handles(rcc, dc, cs)
        with self.frame_cond:
            self.latest_jpeg = None
            self.latest_version = 0
            self.last_frame_time = None
            self.frames = {}
            self.frame_seen_at = {}
            self.frame_versions = {}
            self.frame_cond.notify_all()
        return self.status()

    def shutdown(self) -> None:
        self.stop()

    def wait_for_jpeg(self, after_version: int = 0, timeout: float = 1.0) -> tuple[bytes, int]:
        with self.frame_cond:
            self.frame_cond.wait_for(
                lambda: self.latest_jpeg is not None and self.latest_version > after_version,
                timeout=timeout,
            )
            return self.latest_jpeg or self.placeholder_jpeg, self.latest_version

    def status(self) -> dict[str, Any]:
        with self.lifecycle_lock:
            rcc = self.rcc
            dc = self.dc
            running = self.running
            starting = self.starting
            error = self.error
        rcc_status: dict[str, Any] = {}
        collector_stats: dict[str, Any] = {}
        if rcc is not None:
            try:
                rcc_status = rcc.get_status()
            except Exception as exc:
                rcc_status = {"error": True, "pc": {}, "interrupt_msg": str(exc)}
        if dc is not None:
            try:
                collector_stats = dc.get_stats()
            except Exception:
                collector_stats = {}

        with self.frame_cond:
            frames = {name: dict(meta) for name, meta in self.frames.items()}
            last_frame_age = (
                None if self.last_frame_time is None else max(0.0, time.time() - self.last_frame_time)
            )

        return {
            "running": running,
            "starting": starting,
            "error": error,
            "camera_count": len(frames),
            "last_frame_age_sec": last_frame_age,
            "frames": frames,
            "rcc": rcc_status,
            "collector_stats": collector_stats,
            "config": {
                "camera_fps": self.camera_fps,
                "ui_fps": self.ui_fps,
                "jpeg_quality": self.jpeg_quality,
                "launch_clients": self.launch_clients,
            },
        }

    def _collect_loop(self) -> None:
        assert self.dc is not None
        period = 1.0 / self.ui_fps
        while not self.collect_stop.is_set():
            started = time.monotonic()
            try:
                all_data = self.dc.get_data()
                img_dict: dict[str, Any] = {}
                img_text: dict[str, str] = {}
                frames: dict[str, dict[str, Any]] = {}
                now = time.time()
                with self.frame_cond:
                    frame_seen_at = dict(self.frame_seen_at)
                    frame_versions = dict(self.frame_versions)

                for item_name, item_data in sorted(all_data.items()):
                    if item_data.get("type") != "image":
                        continue
                    image_bytes = item_data.get("data")
                    if not image_bytes:
                        continue
                    image = self.cv2.imdecode(
                        self.np.frombuffer(image_bytes, self.np.uint8),
                        self.cv2.IMREAD_COLOR,
                    )
                    if image is None:
                        continue

                    name = str(item_name)
                    frame_id = self._as_int(item_data.get("frame_id"), 0)
                    seq = self._as_int(item_data.get("seq"), None)
                    version = (frame_id, seq)
                    if frame_versions.get(name) != version:
                        frame_versions[name] = version
                        frame_seen_at[name] = now
                    receive_age_ms = max(0.0, (now - frame_seen_at.get(name, now)) * 1000.0)

                    img_dict[name] = image
                    img_text[name] = f"fid {frame_id}"
                    frames[name] = {
                        "frame_id": frame_id,
                        "pc": str(item_data.get("pc", "")),
                        "src": str(item_data.get("src", "")),
                        "seq": seq,
                        "receive_age_ms": receive_age_ms,
                    }

                if img_dict:
                    merged_image = self.merge_image(img_dict, img_text)
                    ok, encoded = self.cv2.imencode(
                        ".jpg",
                        merged_image,
                        [int(self.cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
                    )
                    if ok:
                        with self.frame_cond:
                            self.latest_jpeg = encoded.tobytes()
                            self.latest_version += 1
                            self.last_frame_time = time.time()
                            self.frames = frames
                            self.frame_seen_at = {
                                name: seen_at for name, seen_at in frame_seen_at.items() if name in frames
                            }
                            self.frame_versions = {
                                name: version for name, version in frame_versions.items() if name in frames
                            }
                            self.frame_cond.notify_all()
            except Exception as exc:
                with self.lifecycle_lock:
                    self.error = str(exc)
            elapsed = time.monotonic() - started
            self.collect_stop.wait(max(0.0, period - elapsed))

    def _cleanup_handles(
        self,
        rcc: Any | None,
        dc: Any | None,
        cs: Any | None,
    ) -> None:
        for label, func in (
            ("rcc.stop", lambda: rcc.stop() if rcc is not None else None),
            ("rcc.end", lambda: rcc.end() if rcc is not None else None),
            ("dc.end", lambda: dc.end() if dc is not None else None),
            ("cs.end", lambda: cs.end() if cs is not None else None),
        ):
            try:
                func()
            except Exception as exc:
                print(f"[camera-live-monitor] {label} failed: {exc}", file=sys.stderr)

    @staticmethod
    def _as_int(value: Any, default: int | None) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _make_placeholder(self, message: str) -> bytes:
        image = self.np.full((720, 1280, 3), (247, 250, 251), dtype=self.np.uint8)
        self.cv2.rectangle(image, (40, 40), (1240, 680), (219, 226, 231), 2)
        self.cv2.putText(
            image,
            "Paradex Camera Monitor",
            (72, 330),
            self.cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (32, 34, 37),
            3,
            self.cv2.LINE_AA,
        )
        self.cv2.putText(
            image,
            message,
            (76, 385),
            self.cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (95, 105, 114),
            2,
            self.cv2.LINE_AA,
        )
        ok, encoded = self.cv2.imencode(".jpg", image, [int(self.cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return b""
        return encoded.tobytes()


class CameraMonitorServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], monitor: CameraMonitor):
        super().__init__(server_address, CameraMonitorHandler)
        self.monitor = monitor


class CameraMonitorHandler(BaseHTTPRequestHandler):
    server: CameraMonitorServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(HTML)
        elif path == "/api/status":
            self._send_json(self.server.monitor.status())
        elif path == "/stream.mjpg":
            self._send_mjpeg()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/start":
            status = self.server.monitor.start()
            code = HTTPStatus.INTERNAL_SERVER_ERROR if status.get("error") else HTTPStatus.OK
            self._send_json(status, code)
        elif path == "/api/stop":
            self._send_json(self.server.monitor.stop())
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[camera-live-monitor] {self.address_string()} - {fmt % args}")

    def _send_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, body: dict[str, Any], code: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_mjpeg(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_version = 0
        while True:
            try:
                jpeg, last_version = self.server.monitor.wait_for_jpeg(
                    after_version=last_version,
                    timeout=2.0,
                )
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii"))
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a browser UI for the distributed Paradex multi-camera preview.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP bind host.")
    parser.add_argument("--port", type=int, default=8792, help="HTTP bind port.")
    parser.add_argument("--pc", action="append", dest="pcs", help="Capture PC name. Repeat to override system/current.")
    parser.add_argument("--camera-fps", type=int, default=10, help="Camera acquisition FPS for preview.")
    parser.add_argument("--ui-fps", type=int, default=10, help="MJPEG refresh FPS.")
    parser.add_argument("--jpeg-quality", type=int, default=72, help="Merged preview JPEG quality, 1-100.")
    parser.add_argument("--auto-start", action="store_true", help="Start streaming when the server boots.")
    parser.add_argument("--no-launch-clients", action="store_true", help="Assume stream_client.py is already running.")
    parser.add_argument("--remote-log", action="store_true", help="Write remote stream_client output to test.log.")
    parser.add_argument(
        "--client-command",
        default="python src/capture/camera/stream_client.py",
        help="Command SSH-launched on capture PCs.",
    )
    parser.add_argument("--command-timeout-ms", type=int, default=2000, help="Stop-command timeout per capture PC.")
    parser.add_argument("--command-retries", type=int, default=1, help="Stop-command retries per capture PC.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    monitor = CameraMonitor(
        pc_list=args.pcs,
        camera_fps=args.camera_fps,
        ui_fps=args.ui_fps,
        jpeg_quality=args.jpeg_quality,
        launch_clients=not args.no_launch_clients,
        client_command=args.client_command,
        remote_log=args.remote_log,
        command_timeout_ms=args.command_timeout_ms,
        command_retries=args.command_retries,
    )
    server = CameraMonitorServer((args.host, args.port), monitor)
    print(f"[camera-live-monitor] open http://{args.host}:{args.port}")
    if args.auto_start:
        threading.Thread(target=monitor.start, name="camera-live-monitor-autostart", daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n[camera-live-monitor] stopping")
    finally:
        server.server_close()
        monitor.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
